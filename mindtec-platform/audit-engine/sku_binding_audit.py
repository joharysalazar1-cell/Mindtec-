"""Read-only signals for exported SKU bindings; never infer stock or fraud."""
import argparse
import hashlib
import json
import re
from pathlib import Path

import collection_adapter
import invoice_adapter

VERSION = 'sku-binding-audit/1.0.0'


def normalized(value):
    return ' '.join(str(value or '').casefold().split())


def label_brand(label, brands):
    text = normalized(label)
    matches = [b for b in brands if text == normalized(b) or
               re.match(re.escape(normalized(b)) + r'(?=\W)', text)]
    if not matches:
        return None
    longest = max(len(normalized(b)) for b in matches)
    winners = {normalized(b): b for b in matches if len(normalized(b)) == longest}
    return next(iter(winners.values())) if len(winners) == 1 else None


def audit(cut, configuration):
    if configuration.get('schema') != 'mindtec-observed-client-core-configuration/1':
        raise ValueError('Explicit observed client configuration required')
    clients = configuration.get('clients', [])
    ids = [c['id'] for c in clients]
    if not clients or len(set(ids)) != len(ids):
        raise ValueError('Distinct nonempty client IDs required')
    for client in clients:
        if not client['id'] or not isinstance(client.get('core_skus'), list) or any(
                not isinstance(s, str) or not s.strip() for s in client['core_skus']):
            raise ValueError('Invalid client SKU list')
    table = next(t for t in cut['tables'] if t['sheet'] == 'Colecta · marcas')
    if table.get('formula_cells_using_cached_values'):
        raise ValueError('Formula caches cannot support observed bindings')
    required = ['ID envío', 'Mes', 'Marca', 'SKUs (códigos Kobo)', 'SKUs (maestro)']
    if any(h not in table['headers'] for h in required):
        raise ValueError('Missing binding columns')
    rows = collection_adapter.table_rows(table)
    brands = sorted({r['values']['Marca'] for r in rows if r['values']['Marca']})
    findings = []
    observed_labels = set()
    for row in rows:
        values, coordinates = row['values'], row['coordinates']
        codes = str(values['SKUs (códigos Kobo)'] or '').split()
        labels = [s.strip() for s in str(values['SKUs (maestro)'] or '').split(' | ') if s.strip()]
        observed_labels.update(normalized(s) for s in labels)
        signals = []
        if len(codes) != len(labels):
            signals.append('code_label_cardinality_unresolved')
        conflicts = []
        for label in labels:
            inferred = label_brand(label, brands)
            if inferred and normalized(inferred) != normalized(values['Marca']):
                conflicts.append({'label': label, 'literal_brand_prefix': inferred})
        if conflicts:
            signals.append('possible_cross_brand_label_binding')
        if signals:
            findings.append({'sheet': table['sheet'], 'source_row': row['source_row'],
                             'original_sha256': cut['provenance']['original_sha256'],
                             'values': {h: values[h] for h in required},
                             'coordinates': {h: coordinates[h] for h in required},
                             'codes': codes, 'labels': labels, 'signals': signals,
                             'conflicts': conflicts, 'review_status': 'pending',
                             'positional_pairing_performed': False})
    current = [{'client_id': c['id'], 'name': c.get('name'),
                'historical_applicability': 'not_established',
                'skus': [{'name': s, 'literal_name_seen_in_export': normalized(s) in observed_labels}
                         for s in c['core_skus']]} for c in clients]
    return {'schema': 'mindtec-sku-binding-audit/1', 'version': VERSION,
            'scope': 'Current configuration and retained export; no historical rule certification',
            'limitations': ['Signals require review; no fraud conclusion',
                            'Literal name occurrence does not prove stock or core compliance',
                            'Codes and labels are never positionally paired or corrected',
                            'No survey exclusions or human review decisions are changed'],
            'source': cut['provenance'], 'clients': current,
            'summary': {'brand_rows': len(rows), 'rows_with_signals': len(findings),
                        'cardinality_signals': sum('code_label_cardinality_unresolved' in f['signals'] for f in findings),
                        'cross_brand_signals': sum('possible_cross_brand_label_binding' in f['signals'] for f in findings),
                        'configured_skus': sum(len(c['core_skus']) for c in clients)},
            'findings': findings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook', required=True)
    parser.add_argument('--configuration', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    workbook = Path(args.workbook).read_bytes()
    configuration = Path(args.configuration).read_bytes()
    result = audit(collection_adapter.workbook_tables(args.workbook, workbook),
                   json.loads(configuration.decode('utf-8-sig')))
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    retained = {'source.xlsx': workbook, 'configuration.json': configuration,
                'audit.json': json.dumps(result, ensure_ascii=False, indent=2).encode('utf-8'),
                'sku_binding_audit.py': Path(__file__).read_bytes(),
                'collection_adapter.py': Path(collection_adapter.__file__).read_bytes(),
                'invoice_adapter.py': Path(invoice_adapter.__file__).read_bytes()}
    for name, raw in retained.items():
        (output / name).write_bytes(raw)
    manifest = {name: {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)}
                for name, raw in retained.items()}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps(result['summary']))


if __name__ == '__main__':
    main()
