"""Retain and verify a reproducible local SKU catalog contrast. No network calls."""
import argparse
import hashlib
import json
from pathlib import Path

import collection_adapter
import sku_catalog_contrast

FILES = ('sku_catalog_run.py', 'sku_catalog_contrast.py', 'sku_binding_audit.py',
         'collection_adapter.py', 'invoice_adapter.py')
LOADED = {name: Path(__file__).with_name(name).read_bytes() for name in FILES}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def encode(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2,
                      allow_nan=False).encode('utf-8')


def result(workbook, catalog):
    return sku_catalog_contrast.contrast(
        collection_adapter.workbook_tables('source.xlsx', workbook), catalog)


def verify(directory):
    directory = Path(directory)
    manifest = json.loads((directory / 'manifest.json').read_text(encoding='utf-8'))
    if manifest.get('schema') != 'mindtec-sku-catalog-custody/1':
        raise ValueError('Unknown custody manifest')
    expected = set(FILES) | {'source.xlsx', 'catalog.csv', 'contrast.json'}
    if set(manifest['files']) != expected:
        raise ValueError('Incomplete custody manifest')
    raw = {}
    for name, meta in manifest['files'].items():
        path = directory / name
        if path.is_symlink():
            raise ValueError('Custody file cannot be a symbolic link')
        raw[name] = path.read_bytes()
        if len(raw[name]) != meta['bytes'] or digest(raw[name]) != meta['sha256']:
            raise ValueError('Custody bytes differ: ' + name)
    if any(raw[name] != LOADED[name] for name in FILES):
        raise ValueError('Retained implementation differs from this verifier')
    recomputed = result(raw['source.xlsx'], raw['catalog.csv'])
    if raw['contrast.json'] != encode(recomputed):
        raise ValueError('Retained result differs from recomputation')
    return recomputed


def run(workbook_path, catalog_path, output):
    workbook = Path(workbook_path).read_bytes()
    catalog = Path(catalog_path).read_bytes()
    computed = result(workbook, catalog)
    if any(Path(__file__).with_name(name).read_bytes() != value for name, value in LOADED.items()):
        raise ValueError('Implementation changed during calculation')
    retained = {**LOADED, 'source.xlsx': workbook, 'catalog.csv': catalog,
                'contrast.json': encode(computed)}
    directory = Path(output)
    directory.mkdir(parents=True, exist_ok=False)
    for name, raw in retained.items():
        with (directory / name).open('xb') as handle:
            handle.write(raw)
    manifest = {'schema': 'mindtec-sku-catalog-custody/1',
                'files': {name: {'sha256': digest(raw), 'bytes': len(raw)}
                          for name, raw in retained.items()}}
    with (directory / 'manifest.json').open('xb') as handle:
        handle.write(encode(manifest))
    return verify(directory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook')
    parser.add_argument('--catalog')
    parser.add_argument('--output')
    parser.add_argument('--verify')
    args = parser.parse_args()
    if args.verify:
        if any((args.workbook, args.catalog, args.output)):
            parser.error('--verify cannot be combined with calculation inputs')
        value = verify(args.verify)
    else:
        if not all((args.workbook, args.catalog, args.output)):
            parser.error('--workbook, --catalog and --output are required')
        value = run(args.workbook, args.catalog, args.output)
    print(json.dumps({'custody_verified': True, 'summary': value['summary']}))


if __name__ == '__main__':
    main()
