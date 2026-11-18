"""Link dated original label evidence to normalized rows without changing either."""
from collections import Counter, defaultdict

from collection_adapter import table_rows


def identifier(value):
    if isinstance(value, bool) or value is None:
        raise ValueError('Explicit identity required')
    if not isinstance(value, (int, str)) or not str(value).strip():
        raise ValueError('Invalid identity')
    return str(value).strip()


def compare(labels, normalized, crosswalk):
    if labels.get('schema') != 'mindtec-original-kobo-label-evidence/1':
        raise ValueError('Original Kobo label evidence required')
    ids, seen = {}, set()
    for row in crosswalk['rows']:
        internal, kobo = identifier(row['internal_id']), identifier(row['kobo_id'])
        if internal in ids or kobo in seen:
            raise ValueError('One-to-one explicit identity crosswalk required')
        ids[internal] = kobo
        seen.add(kobo)
    lookup = defaultdict(list)
    for table in labels['tables']:
        if table['kind'] != 'brand_labels':
            continue
        category = table['subcategory_code']
        for record in table['records']:
            key = (identifier(record['_submission__id']['value']), category,
                   record['marca_act_'+category]['value'])
            lookup[key].append((table, record))
    tables = [t for t in normalized['tables'] if t['sheet'] == 'Colecta · marcas']
    if len(tables) != 1:
        raise ValueError('One normalized brands sheet required')
    if tables[0].get('formula_cells_using_cached_values'):
        raise ValueError('Formula cache cannot support normalized observations')
    rows, counts, monthly = [], Counter(), defaultdict(Counter)
    for source in table_rows(tables[0]):
        values = source['values']
        internal = identifier(values['ID envío'])
        key = (ids.get(internal), values['Subcategoría (código)'], values['Marca (código)'])
        candidates = lookup.get(key, [])
        state = ('identity_crosswalk_missing' if internal not in ids else
                 'no_historical_row' if not candidates else
                 'ambiguous_historical_rows' if len(candidates) != 1 else
                 'historical_parent_unresolved' if candidates[0][1]['parent_binding_state'] != 'exact_id_index_version' else
                 'historical_options_unresolved' if candidates[0][1]['invalid_option_values'] else
                 'unique_historical_row_recovered')
        entry = {'internal_id': internal, 'kobo_id': ids.get(internal),
                 'month': values['Mes'], 'subcategory_code': key[1],
                 'brand_code': key[2], 'declared_brand': values['Marca'],
                 'normalized_source_row': source['source_row'],
                 'normalized_coordinates': source['coordinates'],
                 'normalized_codes': values['SKUs (códigos Kobo)'],
                 'normalized_master_labels': values['SKUs (maestro)'],
                 'state': state, 'candidate_count': len(candidates),
                 'automatic_correction': False, 'historical_code_mapping_certified': False}
        if state == 'unique_historical_row_recovered':
            table, record = candidates[0]
            old = {x['label'] for x in record['selected_labels']}
            current = {x.strip() for x in str(values['SKUs (maestro)'] or '').split(' | ') if x.strip()}
            entry.update(original_sheet=table['sheet'], original_row=record['source_row'],
                         original_version=record['_submission___version__'],
                         selected_label_cells=record['selected_labels'],
                         original_parent_row=record['parent_source_row'],
                         literal_label_sets_equal=old == current,
                         selected_label_count=len(record['selected_labels']))
        rows.append(entry)
        counts[state] += 1
        monthly[values['Mes']][state] += 1
    return {'schema': 'mindtec-historical-sku-label-contrast/1',
            'original_workbook_sha256': labels['original_sha256'],
            'normalized_workbook_sha256': normalized['provenance']['original_sha256'],
            'summary': {'normalized_brand_rows': len(rows), 'states': dict(counts),
                        'monthly_states': {k: dict(v) for k, v in sorted(monthly.items())},
                        'recovered_rows_with_different_literal_label_sets': sum(
                            r.get('literal_label_sets_equal') is False for r in rows)},
            'limits': ['Dated original labels do not replace later Scan corrections',
                       'No positional code-to-label pairing or automatic correction',
                       'A recovered row does not certify current core-SKU compliance'],
            'rows': rows}
