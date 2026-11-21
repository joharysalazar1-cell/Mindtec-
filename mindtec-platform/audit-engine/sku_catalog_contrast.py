"""Contrast export codes with a dated catalog without rewriting historical labels."""
import csv
import hashlib
import io
import json
import re
from collections import defaultdict

from sku_binding_audit import normalized
from collection_adapter import table_rows


def contrast(cut, catalog_raw):
    reader = csv.DictReader(io.StringIO(catalog_raw.decode('utf-8-sig')), delimiter=';')
    required = {'Código en Kobo', 'Marca', 'Valor del catálogo'}
    if not required.issubset(reader.fieldnames or []):
        raise ValueError('Catalog code, brand and label columns required')
    if len(set(reader.fieldnames)) != len(reader.fieldnames):
        raise ValueError('Duplicate catalog headers')
    catalog = list(reader)
    index = defaultdict(list)
    for line, row in enumerate(catalog, 2):
        if None in row or any(row.get(h) is None for h in required):
            raise ValueError('Malformed catalog record')
        code = row['Código en Kobo'].strip()
        if code:
            index[code].append({'csv_record_number': line, 'code': code,
                                'brand': row['Marca'], 'label': row['Valor del catálogo']})
    table = next(t for t in cut['tables'] if t['sheet'] == 'Colecta · marcas')
    if table.get('formula_cells_using_cached_values'):
        raise ValueError('Formula cache is not observed evidence')
    rows = []
    counts = defaultdict(int)
    monthly = defaultdict(lambda: defaultdict(int))
    for source in table_rows(table):
        values = source['values']
        month = values.get('Mes')
        if not isinstance(month, str) or not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month):
            raise ValueError('Explicit YYYY-MM required for every brand row')
        for code in str(values['SKUs (códigos Kobo)'] or '').split():
            candidates = index.get(code, [])
            if not candidates:
                status = 'code_not_in_dated_catalog'
            elif len(candidates) != 1:
                status = 'ambiguous_catalog_code'
            elif not normalized(candidates[0]['brand']) or not normalized(values['Marca']):
                status = 'missing_brand_evidence'
            elif normalized(candidates[0]['brand']) != normalized(values['Marca']):
                status = 'brand_differs_from_dated_catalog'
            else:
                status = 'brand_matches_dated_catalog'
            counts[status] += 1
            monthly[month][status] += 1
            rows.append({'sheet': table['sheet'], 'source_row': source['source_row'],
                         'source_coordinates': source['coordinates'],
                         'internal_id': values['ID envío'], 'month': values['Mes'],
                         'declared_brand': values['Marca'], 'code': code,
                         'catalog_candidates': candidates, 'status': status,
                         'historical_mapping_certified': False,
                         'automatic_correction': False})
    return {'schema': 'mindtec-sku-dated-catalog-contrast/1',
            'source_workbook_sha256': cut['provenance']['original_sha256'],
            'catalog_sha256': hashlib.sha256(catalog_raw).hexdigest(),
            'limitations': ['Dated catalog does not certify the choice list used by a historical form',
                           'A matching brand does not prove label identity or physical stock',
                           'Different brands indicate a mapping conflict, not fraud'],
            'summary': {'catalog_rows': len(catalog), 'code_occurrences': len(rows),
                        'status_counts': dict(counts),
                        'monthly_status_counts': {m: dict(c) for m, c in sorted(monthly.items())}},
            'rows': rows}
