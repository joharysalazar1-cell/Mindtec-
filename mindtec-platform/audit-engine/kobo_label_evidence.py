"""Read original Kobo label exports by cell coordinate, preserving form versions.

Duplicate unrelated question headers are retained by position, never collapsed.
Selected option labels are independent evidence; no positional code mapping.
"""
import argparse
import hashlib
import io
import json
import re
import zipfile
from collections import Counter
from pathlib import Path

from invoice_adapter import validate_archive, xml_part

M = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
NS = {'m': M}
VERSION = 'kobo-label-evidence/1.0.1'


def extract(raw):
    if len(raw) > 25000000:
        raise ValueError('Maximum workbook size is 25 MB')
    sha = hashlib.sha256(raw).hexdigest()
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        validate_archive(archive)
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            strings = [''.join(t.text or '' for t in si.iter('{'+M+'}t'))
                       for si in xml_part(archive, 'xl/sharedStrings.xml').findall('m:si', NS)]
        rels = {}
        for rel in xml_part(archive, 'xl/_rels/workbook.xml.rels'):
            if rel.attrib.get('TargetMode') == 'External' or rel.attrib['Id'] in rels:
                raise ValueError('External or duplicate workbook relationship')
            target = rel.attrib['Target'].lstrip('/')
            if '..' in target.split('/'):
                raise ValueError('Unsafe worksheet target')
            rels[rel.attrib['Id']] = target if target.startswith('xl/') else 'xl/'+target

        def cells(row, wanted=None):
            output = {}
            for cell in row.findall('m:c', NS):
                coordinate = cell.attrib.get('r', '')
                match = re.fullmatch(r'([A-Z]{1,3})([1-9][0-9]*)', coordinate)
                if not match or match[2] != row.attrib['r']:
                    raise ValueError('Invalid cell coordinate')
                column = match[1]
                if column in output:
                    raise ValueError('Duplicate cell coordinate')
                if wanted is not None and column not in wanted:
                    continue
                if cell.find('m:f', NS) is not None:
                    raise ValueError('Formula cache cannot support original labels')
                value = cell.find('m:v', NS)
                value = value.text if value is not None else ''.join(
                    t.text or '' for t in cell.iter('{'+M+'}t'))
                if cell.attrib.get('t') == 's':
                    if not value or not value.isdigit() or int(value) >= len(strings):
                        raise ValueError('Invalid shared string index')
                    value = strings[int(value)]
                if cell.attrib.get('t') == 'e':
                    raise ValueError('Excel error in original label evidence')
                output[column] = {'coordinate': coordinate, 'value': value,
                                  'excel_type': cell.attrib.get('t', 'number')}
            return output

        tables = []
        book = xml_part(archive, 'xl/workbook.xml')
        names = set()
        for sheet in book.find('m:sheets', NS):
            name = sheet.attrib['name']
            if name in names:
                raise ValueError('Duplicate worksheet name')
            names.add(name)
            if name.startswith('rep_') and not name.startswith(('rep_bsa_', 'rep_lac_')):
                continue
            target = rels[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
            rows = xml_part(archive, target).findall('m:sheetData/m:row', NS)
            if not rows:
                continue
            numbers = [int(r.attrib['r']) for r in rows]
            if numbers != sorted(set(numbers)):
                raise ValueError('Duplicate or unordered worksheet rows')
            headers = cells(rows[0])
            lookup = {}
            for column, cell in headers.items():
                lookup.setdefault(cell['value'], []).append(column)
            def column(label):
                found = lookup.get(label, [])
                if len(found) != 1:
                    raise ValueError('Missing or ambiguous required header: '+label)
                return found[0]
            if not name.startswith('rep_'):
                if '_id' not in lookup or '__version__' not in lookup:
                    continue
                wanted = {key: column(key) for key in ('_id', '__version__', '_index')}
                records = []
                for row in rows[1:]:
                    values = cells(row, set(wanted.values()))
                    records.append({'source_row': int(row.attrib['r']),
                                    **{key: values.get(c) for key, c in wanted.items()}})
                tables.append({'kind': 'parent', 'sheet': name, 'records': records})
                continue
            suffix = name.removeprefix('rep_')
            question = '¿Qué SKUs / presentaciones de ${marca_lbl_'+suffix+'} están disponibles en este punto de venta?'
            if question not in lookup:
                continue
            keys = ['_submission__id', '_submission___version__', '_parent_index',
                    'marca_act_'+suffix, 'marca_lbl_'+suffix]
            wanted = {key: column(key) for key in keys}
            wanted['aggregate_label_text'] = column(question)
            options = {c: h for c, h in headers.items() if h['value'].startswith(question+'/')}
            if not options:
                raise ValueError('No expanded option label columns')
            records = []
            for row in rows[1:]:
                values = cells(row, set(wanted.values()) | set(options))
                selected, invalid = [], []
                for c, header in options.items():
                    cell = values.get(c)
                    if cell is None or cell['value'] in ('', '0', 'false'):
                        continue
                    entry = {'label': header['value'][len(question)+1:],
                             'header_coordinate': header['coordinate'], **cell}
                    (selected if cell['value'] in ('1', 'true') else invalid).append(entry)
                records.append({'source_row': int(row.attrib['r']),
                                **{key: values.get(c) for key, c in wanted.items()},
                                'selected_labels': selected, 'invalid_option_values': invalid})
            tables.append({'kind': 'brand_labels', 'sheet': name, 'subcategory_code': suffix,
                           'option_columns': len(options), 'records': records})
    parents = [t for t in tables if t['kind'] == 'parent']
    if len(parents) != 1:
        raise ValueError('Exactly one original parent submission sheet required')
    index = {}
    for record in parents[0]['records']:
        eid = (record.get('_id') or {}).get('value')
        if not eid or eid in index:
            raise ValueError('Unique nonempty parent Kobo IDs required')
        index[eid] = record
    for table in tables:
        if table['kind'] != 'brand_labels':
            continue
        for record in table['records']:
            eid = (record.get('_submission__id') or {}).get('value')
            parent = index.get(eid)
            version = (record.get('_submission___version__') or {}).get('value')
            same = bool(parent and version and parent.get('__version__') and
                        parent.get('_index') and record.get('_parent_index') and
                        parent['__version__']['value'] == version and
                        parent['_index']['value'] == record['_parent_index']['value'])
            record['parent_binding_state'] = 'exact_id_index_version' if same else 'unresolved'
            record['parent_source_row'] = parent['source_row'] if parent else None
    all_rows = [r for t in tables if t['kind'] == 'brand_labels' for r in t['records']]
    return {'schema': 'mindtec-original-kobo-label-evidence/1', 'version': VERSION,
            'original_sha256': sha, 'tables': tables,
            'summary': {'parent_submissions': len(index), 'brand_repeat_rows': len(all_rows),
                        'selected_label_occurrences': sum(len(r['selected_labels']) for r in all_rows),
                        'unresolved_parent_bindings': sum(r['parent_binding_state'] != 'exact_id_index_version' for r in all_rows),
                        'invalid_option_values': sum(len(r['invalid_option_values']) for r in all_rows),
                        'form_versions': dict(Counter((r.get('__version__') or {}).get('value') for r in index.values()))},
            'limits': ['Historical original export; does not replace later corrections',
                       'Selected labels do not certify a universal code-to-label mapping',
                       'No physical-stock truth or fraud conclusion inferred']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workbook', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    raw = Path(args.workbook).read_bytes()
    result = extract(raw)
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    files = {'original.xlsx': raw, 'labels.json': json.dumps(result, ensure_ascii=False, indent=2).encode('utf-8'),
             'kobo_label_evidence.py': Path(__file__).read_bytes(),
             'invoice_adapter.py': Path(__file__).with_name('invoice_adapter.py').read_bytes()}
    for name, content in files.items():
        (output/name).write_bytes(content)
    (output/'manifest.json').write_text(json.dumps({n: hashlib.sha256(v).hexdigest() for n, v in files.items()}, indent=2), encoding='utf-8')
    print(json.dumps(result['summary']))
