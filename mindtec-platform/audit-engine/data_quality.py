"""Source-bound technical quality measures; unavailable controls never become zero.

Purchase-document lines are not a POS ledger or a physical inventory.
"""
import collections
import csv
import io
import invoice_core
from engine import canonical, sha
import engine

VERSION = 'document-data-quality/1.0.0'
CRITICAL = ('ID SKU', 'Sticker', 'Fecha de emisión', 'Precio unitario', 'Costo unitario')


def fraction(numerator, denominator):
    return {'numerator': numerator, 'denominator': denominator, 'percentage': 100*numerator/denominator if denominator else None}


def catalogue_codes(raw):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')), delimiter=';')
    if not reader.fieldnames or len(set(reader.fieldnames)) != len(reader.fieldnames) or 'Código en Kobo' not in reader.fieldnames:
        raise ValueError('Distinct catalogue headers and explicit Kobo code required')
    codes = collections.Counter()
    for row in reader:
        if None in row or any(value is None for value in row.values()):
            raise ValueError('Catalogue row width differs')
        code = row['Código en Kobo']
        if not invoice_core.empty(code):
            codes[code] += 1
    return codes


def evaluate(cut, catalogue_raw=None, *, source_raw=None):
    invoice_core.validate_cut(cut)
    canonical_sha = sha(canonical(cut)); source_sha = None
    if source_raw is not None:
        if canonical(engine.load_json_bytes(source_raw)) != canonical(cut):
            raise ValueError('Supplied raw source differs from evaluated cut')
        source_sha = sha(source_raw)
    provenance = cut.get('provenance', {})
    codes = catalogue_codes(catalogue_raw) if catalogue_raw is not None else None
    values = invoice_core.row_values(cut); findings = []
    headers = set(cut['headers']); supported_dates = provenance.get('date_system') == 'excel_1900'
    def evidence(indices, fields):
        return {'source_cut_sha256': source_sha, 'canonical_cut_sha256': canonical_sha, 'original_workbook_sha256': provenance.get('original_sha256'), 'worksheet': provenance.get('worksheet'), 'source_rows': [cut['rows'][i]['source_row'] for i in indices], 'line_keys': [invoice_core.line_key(values[i]) for i in indices], 'fields': fields, 'original_values': [{field: values[i].get(field) for field in fields} for i in indices]}
    def emit(rule, indices, fields):
        e = evidence(indices, fields)
        f = {'rule': rule, 'rule_version': VERSION, 'severity': 'review', 'evidence': e, 'disposition': 'needs_human_review', 'interpretation': 'Technical signal only; no automatic correction or fraud inference.'}
        f['fingerprint'] = sha(canonical(f)); findings.append(f)
    # Findings are generated once, not once per monthly and total aggregate.
    keys = collections.defaultdict(list)
    for i, row in enumerate(values):
        missing = [field for field in CRITICAL if field in headers and invoice_core.empty(row[field])]
        if missing: emit('critical_value_missing', [i], missing)
        key = invoice_core.line_key(row)
        if key is None: emit('line_identity_missing', [i], ['ID factura', 'Línea'])
        else: keys[key].append(i)
        for field in ['Precio unitario', 'Cantidad', 'Total neto']:
            if field in headers and not invoice_core.empty(row[field]) and invoice_core.number(row[field]) is None:
                emit('numeric_format_invalid', [i], [field])
        if supported_dates and 'Fecha de emisión' in headers and not invoice_core.empty(row['Fecha de emisión']) and invoice_core.date(row['Fecha de emisión'], 'excel_1900') is None:
            emit('document_date_invalid', [i], ['Fecha de emisión'])
        if row['Mes'] not in cut['scope']['periods']:
            emit('period_outside_declared_scope', [i], ['Mes'])
        if codes is not None and 'Código Kobo SKU' in headers:
            code = row['Código Kobo SKU']
            if not invoice_core.empty(code):
                if not isinstance(code, str): emit('catalogue_code_type_unresolved', [i], ['Código Kobo SKU'])
                elif not codes.get(code): emit('code_absent_from_dated_catalogue', [i], ['Código Kobo SKU'])
                elif codes[code] > 1: emit('catalogue_code_ambiguous', [i], ['Código Kobo SKU'])
    for indices in keys.values():
        if len(indices) > 1: emit('duplicate_line_key', indices, ['ID factura', 'Línea'])
    buckets = {month: [i for i, row in enumerate(values) if row['Mes'] == month] for month in cut['scope']['periods']}
    outside = [i for i, row in enumerate(values) if row['Mes'] not in cut['scope']['periods']]
    if outside: buckets['outside_declared_scope'] = outside
    buckets['TOTAL'] = list(range(len(values)))
    periods = []
    for period, indices in buckets.items():
        rows = [values[i] for i in indices]; n = len(rows); local_keys = collections.Counter(invoice_core.line_key(r) for r in rows if invoice_core.line_key(r) is not None)
        nulls = {field: ({'state': 'evaluated', **fraction(sum(invoice_core.empty(r[field]) for r in rows), n)} if field in headers else {'state': 'field_absent', 'numerator': None, 'denominator': None, 'percentage': None}) for field in CRITICAL}
        missing_rows = sum(any(invoice_core.empty(r[field]) for field in CRITICAL if field in headers) for r in rows)
        numeric = {}
        for field in ['Precio unitario', 'Cantidad', 'Total neto']:
            if field not in headers:
                numeric[field] = {'state': 'field_absent'}; continue
            filled = [r[field] for r in rows if not invoice_core.empty(r[field])]; parsed = [invoice_core.number(v) for v in filled]; known = [v for v in parsed if v is not None]
            numeric[field] = {'state': 'evaluated', 'missing': n-len(filled), 'invalid_format': fraction(sum(v is None for v in parsed), len(filled)), 'zero': fraction(sum(v == 0 for v in known), len(known)), 'negative': fraction(sum(v < 0 for v in known), len(known))}
        date_values = [r['Fecha de emisión'] for r in rows if 'Fecha de emisión' in headers and not invoice_core.empty(r['Fecha de emisión'])]
        dates = {'state': 'evaluated', 'missing': n-len(date_values), **fraction(sum(invoice_core.date(v, 'excel_1900') is None for v in date_values), len(date_values))} if supported_dates and 'Fecha de emisión' in headers else {'state': 'date_system_or_field_not_supported', 'percentage': None}
        reference = {'state': 'catalogue_not_provided' if codes is None else 'code_field_absent', 'percentage': None}
        if codes is not None and 'Código Kobo SKU' in headers:
            present = [r['Código Kobo SKU'] for r in rows if not invoice_core.empty(r['Código Kobo SKU'])]; evaluable = [c for c in present if isinstance(c, str)]
            reference = {'state': 'partial_code_existence_only', 'code_presence': fraction(len(present), n), 'invalid_code_type': len(present)-len(evaluable), 'absent_in_catalogue': fraction(sum(c not in codes for c in evaluable), len(evaluable)), 'ambiguous_in_catalogue': fraction(sum(codes.get(c, 0)>1 for c in evaluable), len(evaluable)), 'not_full_sku_or_store_id_integrity': True}
        periods.append({'period': period, 'lines': n, 'documents_with_id': len({str(r['ID factura']) for r in rows if not invoice_core.empty(r['ID factura'])}), 'completeness': {'state': 'partial' if any(field not in headers for field in CRITICAL) else 'evaluated', 'fields': nulls, 'rows_with_any_available_critical_null': fraction(missing_rows, n)}, 'uniqueness': {'missing_key': fraction(sum(invoice_core.line_key(r) is None for r in rows), n), 'duplicate_excess_rows': fraction(sum(count-1 for count in local_keys.values()), n), 'duplicate_involved_rows': fraction(sum(count for count in local_keys.values() if count > 1), n), 'key': ['ID factura','Línea']}, 'numeric_formats': numeric, 'document_dates': dates, 'referential_code_existence': reference})
    return {'schema': 'mindtec-document-data-quality/1', 'version': VERSION, 'source_cut_sha256': source_sha, 'canonical_cut_sha256': canonical_sha, 'original_provenance': provenance, 'scope': cut['scope'], 'catalogue_sha256': sha(catalogue_raw) if catalogue_raw is not None else None, 'periods': periods, 'findings': findings, 'limits': ['Null completeness measures available fields, not overall reliability.', 'Line-key uniqueness does not exclude the same document captured with another ID.', 'Code existence in a dated catalogue does not certify historical SKU meaning or full foreign-key integrity.', 'No financial reconciliation, margins, inventory balance, customer identity or fraud determination is asserted.']}
