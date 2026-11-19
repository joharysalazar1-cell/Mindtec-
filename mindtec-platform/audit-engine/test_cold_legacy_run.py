import copy
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from xml.sax.saxutils import escape

import cold_legacy_reference as cold
import cold_legacy_run as runner
from test_cold_legacy_reference import fixture


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.source = self.root/'cold.json'; self.workbook = self.root/'detail.xlsx'; self.output = self.root/'custody'
        s = fixture(); old = list(s['answer_evidence'].items()); headers = []; values = []
        for index, (_, answer) in enumerate(old):
            col = chr(65+index); headers.append('<c r="'+col+'1" t="inlineStr"><is><t>'+escape(answer['route'])+'</t></is></c>')
            value = answer['value']
            values.append('<c r="'+col+'2"'+('><v>'+str(value)+'</v></c>' if isinstance(value, int) else ' t="inlineStr"><is><t>'+escape(value)+'</t></is></c>'))
        with zipfile.ZipFile(self.workbook, 'w') as z:
            z.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Envíos" sheetId="1" r:id="r1"/></sheets></workbook>')
            z.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr('xl/worksheets/sheet1.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData><row r="1">'+''.join(headers)+'</row><row r="2">'+''.join(values)+'</row></sheetData></worksheet>')
        s['source_sha256'] = runner.sha(self.workbook.read_bytes()); s['cells'] = {}; s['answer_evidence'] = {}; ids = []
        for index, (_, answer) in enumerate(old):
            cell = {'source_sha256': s['source_sha256'], 'sheet': 'Envíos', 'coordinate': chr(65+index)+'2', 'source_row': 2, 'column': answer['route'], 'kobo_id': '1', 'value': answer['value']}
            cid = cold.digest(cell); s['cells'][cid] = cell; answer['cell_ids'] = [cid]; aid = cold.digest(answer); s['answer_evidence'][aid] = answer; ids.append(aid)
        for inv in s['category_inventories']: inv['answer_ids'] = ids
        s.update(schema='mindtec-declared-cold-share/1', version='declared-cold-share/1.1.0', monthly=[{'brand_code': 'a', 'brand': 'A'}, {'brand_code': 'b', 'brand': 'B'}])
        self.data = s; self.source.write_bytes(runner.encode(s))

    def run_custody(self):
        return runner.run(self.source, self.workbook, self.output, runner.sha(self.source.read_bytes()))

    def test_roundtrip_checks_original_and_preserves_inputs(self):
        before = self.source.read_bytes(), self.workbook.read_bytes(); self.run_custody(); result = runner.verify(self.output)
        self.assertEqual(result['monthly'][0]['whole_cohort_share'], 25)
        self.assertEqual((self.source.read_bytes(), self.workbook.read_bytes()), before)
        with self.assertRaises(FileExistsError): self.run_custody()

    def test_wrong_pin_or_workbook_creates_no_custody(self):
        with self.assertRaises(ValueError): runner.run(self.source, self.workbook, self.output, '0'*64)
        self.assertFalse(self.output.exists()); self.workbook.write_bytes(b'wrong')
        with self.assertRaises(ValueError): self.run_custody()
        self.assertFalse(self.output.exists())

    def test_rehashed_fabricated_result_is_detected_by_replay(self):
        self.run_custody(); path = self.output/'result.json'; path.write_bytes(b'{}'); mp = self.output/'manifest.json'; m = json.loads(mp.read_bytes()); m['files']['result.json'] = {'sha256': runner.sha(b'{}'), 'bytes': 2}; mp.write_bytes(runner.encode(m))
        with self.assertRaises(ValueError): runner.verify(self.output)

    def test_rehashed_false_original_coordinate_is_detected(self):
        source = copy.deepcopy(self.data); old_id, cell = next(iter(source['cells'].items())); cell['column'] = 'Not the original question'; new_id = cold.digest(cell); source['cells'] = {**source['cells'], new_id: cell}; del source['cells'][old_id]
        for inv in source['category_inventories']:
            rebuilt = []
            for aid in inv['answer_ids']:
                answer = copy.deepcopy(source['answer_evidence'][aid])
                answer['cell_ids'] = [new_id if cid == old_id else cid for cid in answer['cell_ids']]; new_aid = cold.digest(answer); source['answer_evidence'][new_aid] = answer; rebuilt.append(new_aid)
            inv['answer_ids'] = rebuilt
        with self.assertRaises(ValueError): runner.calculate(runner.encode(source), self.workbook.read_bytes())

    def test_missing_implementation_dependency_is_rejected(self):
        self.run_custody(); mp = self.output/'manifest.json'; m = json.loads(mp.read_bytes()); del m['files']['invoice_adapter.py']; mp.write_bytes(runner.encode(m))
        with self.assertRaises(ValueError): runner.verify(self.output)


if __name__ == '__main__': unittest.main()
