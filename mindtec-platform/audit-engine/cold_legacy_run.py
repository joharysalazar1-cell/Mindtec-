"""Seal and replay the legacy cold reference against its exact original workbook.

No network, input modification, observer restart or automatic publication.
"""
import argparse
import hashlib
import json
from pathlib import Path

import collection_adapter
import cold_legacy_reference

FILES = ('cold_legacy_run.py', 'cold_legacy_reference.py', 'collection_adapter.py', 'invoice_adapter.py')
LOADED = {name: Path(__file__).with_name(name).read_bytes() for name in FILES}
INPUTS = {'cold-result.json', 'source.xlsx'}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def calculate(source_raw, workbook_raw):
    source = json.loads(source_raw)
    if source.get('schema') != 'mindtec-declared-cold-share/1' or source.get('version') != 'declared-cold-share/1.1.0':
        raise ValueError('Supported original cold-result schema and version required')
    if sha(workbook_raw) != source['source_sha256']:
        raise ValueError('Original workbook hash differs')
    catalogue = [{'brand_code': code, 'brand': name} for code, name in sorted({(s['brand_code'], s['brand']) for s in source['monthly']})]
    result = cold_legacy_reference.reconstruct(source, catalogue)
    book = collection_adapter.workbook_tables('source.xlsx', workbook_raw)
    tables = [t for t in book['tables'] if t['sheet'] == 'Envíos']
    if len(tables) != 1:
        raise ValueError('One original Envíos sheet required')
    table = tables[0]
    values = {coordinate: (value, row['source_row']) for row in table['rows'] for coordinate, value in zip(row['coordinates'], row['cells']) if coordinate}
    headers = dict(zip(table['header_coordinates'], table['headers']))
    for cell in result['cells'].values():
        coordinate = cell['coordinate']; header = ''.join(c for c in coordinate if c.isalpha())+str(table['header_row'])
        if cell['sheet'] != table['sheet'] or coordinate not in values or values[coordinate] != (cell['value'], cell['source_row']) or headers.get(header) != cell['column']:
            raise ValueError('Original cell or header differs')
    return result


def verify(directory):
    directory = Path(directory).resolve()
    manifest = json.loads((directory/'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 'mindtec-legacy-cold-custody/1' or set(manifest['files']) != set(FILES) | INPUTS | {'result.json'}:
        raise ValueError('Complete supported custody required')
    retained = {}
    for name, meta in manifest['files'].items():
        path = directory/name
        if path.is_symlink():
            raise ValueError('Symbolic evidence file rejected')
        raw = path.read_bytes()
        if sha(raw) != meta['sha256'] or len(raw) != meta['bytes']:
            raise ValueError('Retained bytes differ: '+name)
        retained[name] = raw
    if any(retained[name] != LOADED[name] for name in FILES):
        raise ValueError('Retained implementation differs from verifier')
    computed = calculate(retained['cold-result.json'], retained['source.xlsx'])
    if retained['result.json'] != encode(computed):
        raise ValueError('Result differs from recomputation')
    return computed


def run(source_path, workbook_path, output, expected_source_sha256):
    source_path = Path(source_path).resolve(); workbook_path = Path(workbook_path).resolve(); output = Path(output).resolve()
    if source_path.is_relative_to(output) or workbook_path.is_relative_to(output):
        raise ValueError('Inputs must be outside custody')
    source_raw = source_path.read_bytes(); workbook_raw = workbook_path.read_bytes()
    if sha(source_raw) != expected_source_sha256:
        raise ValueError('Pinned cold-result hash differs')
    result = calculate(source_raw, workbook_raw)
    if any(Path(__file__).with_name(name).read_bytes() != raw for name, raw in LOADED.items()):
        raise ValueError('Implementation changed during calculation')
    files = {**LOADED, 'cold-result.json': source_raw, 'source.xlsx': workbook_raw, 'result.json': encode(result)}
    output.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (output/name).open('xb') as handle:
            handle.write(raw)
    manifest = {'schema': 'mindtec-legacy-cold-custody/1', 'version': cold_legacy_reference.VERSION, 'network_delivery': False, 'scope': result['scope'], 'files': {name: {'sha256': sha(raw), 'bytes': len(raw)} for name, raw in files.items()}}
    with (output/'manifest.json').open('xb') as handle:
        handle.write(encode(manifest))
    verify(output)
    return {'custody': str(output), 'source_sha256': result['source_sha256'], 'result_sha256': sha(files['result.json']), 'visits': len(result['stores']), 'verified_original_cells': len(result['cells']), 'network_delivery': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--verify', type=Path)
    parser.add_argument('--cold-result', type=Path)
    parser.add_argument('--workbook', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--expected-result-sha256')
    args = parser.parse_args()
    if args.verify:
        verified = verify(args.verify)
        print(encode({'verified': True, 'visits': len(verified['stores']), 'cells': len(verified['cells'])}).decode())
    else:
        if not all((args.cold_result, args.workbook, args.output, args.expected_result_sha256)):
            parser.error('All source, workbook, output and pinned hash arguments are required')
        print(encode(run(args.cold_result, args.workbook, args.output, args.expected_result_sha256)).decode())
