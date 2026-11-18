import json
from pathlib import Path
import tempfile
import unittest
import zipfile
from xml.sax.saxutils import escape

import sku_catalog_run as runner


class CatalogCustodyTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.workbook = self.root / 'source.xlsx'
        headers = ['ID envío', 'Mes', 'Marca', 'SKUs (códigos Kobo)', 'SKUs (maestro)']
        data = [headers, ['1', '2026-09', 'Red Bull', 'sku_1', 'Tampico 3 L']]
        rows = ''.join('<row r="%s">%s</row>' % (i, ''.join(
            '<c r="%s%s" t="inlineStr"><is><t>%s</t></is></c>' % (chr(65+j), i, escape(v))
            for j, v in enumerate(values))) for i, values in enumerate(data, 1))
        with zipfile.ZipFile(self.workbook, 'w') as z:
            z.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Colecta · marcas" sheetId="1" r:id="r1"/></sheets></workbook>')
            z.writestr('xl/_rels/workbook.xml.rels', '<Relationships><Relationship Id="r1" Target="worksheets/sheet1.xml"/></Relationships>')
            z.writestr('xl/worksheets/sheet1.xml', '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'+rows+'</sheetData></worksheet>')
        self.catalog = self.root / 'catalog.csv'
        self.catalog.write_text('Código en Kobo;Marca;Valor del catálogo\nsku_1;Tampico;Tampico 3 L\n', encoding='utf-8')
        self.output = self.root / 'run'

    def test_roundtrip_and_no_overwrite(self):
        value = runner.run(self.workbook, self.catalog, self.output)
        self.assertEqual(runner.verify(self.output), value)
        with self.assertRaises(FileExistsError):
            runner.run(self.workbook, self.catalog, self.output)

    def test_modified_source_rejected(self):
        runner.run(self.workbook, self.catalog, self.output)
        (self.output / 'catalog.csv').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            runner.verify(self.output)

    def test_rehashed_fabricated_result_rejected(self):
        runner.run(self.workbook, self.catalog, self.output)
        path = self.output / 'contrast.json'
        path.write_bytes(b'{}')
        manifest = json.loads((self.output / 'manifest.json').read_text())
        manifest['files']['contrast.json'] = {'bytes': 2, 'sha256': runner.digest(b'{}')}
        (self.output / 'manifest.json').write_bytes(runner.encode(manifest))
        with self.assertRaises(ValueError):
            runner.verify(self.output)

    def test_missing_dependency_rejected(self):
        runner.run(self.workbook, self.catalog, self.output)
        manifest = json.loads((self.output / 'manifest.json').read_text())
        del manifest['files']['sku_binding_audit.py']
        (self.output / 'manifest.json').write_bytes(runner.encode(manifest))
        with self.assertRaises(ValueError):
            runner.verify(self.output)


if __name__ == '__main__':
    unittest.main()
