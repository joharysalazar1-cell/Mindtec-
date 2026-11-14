import io,tempfile,unittest,warnings,zipfile
from pathlib import Path
from invoice_adapter import workbook_cut
from test_invoice_pipeline import fixture_book
from test_invoices import SCOPE

class XlsxSafetyTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'test.xlsx';fixture_book(self.path,53.33)
 def tearDown(self):self.tmp.cleanup()
 def rewrite(self,transform,extra=None):
  with zipfile.ZipFile(self.path) as z:parts=[(n,z.read(n)) for n in z.namelist()]
  with zipfile.ZipFile(self.path,'w',zipfile.ZIP_DEFLATED) as z:
   for n,b in parts:z.writestr(n,transform(n,b))
   if extra:
    with warnings.catch_warnings():
     warnings.simplefilter('ignore');z.writestr(*extra)
 def reject(self,pattern):
  with self.assertRaisesRegex(ValueError,pattern):workbook_cut(self.path,SCOPE)
 def test_duplicate_zip_entry(self):
  self.rewrite(lambda n,b:b,('xl/workbook.xml',b'<other/>'));self.reject('Duplicate ZIP')
 def test_unsafe_archive_paths(self):
  self.rewrite(lambda n,b:b,('../other.xml',b'<other/>'));self.reject('Unsafe workbook')
 def test_dtd_in_utf8_and_utf16(self):
  original=self.path.read_bytes()
  for encoding in ['utf-8','utf-16']:
   with self.subTest(encoding=encoding):
    self.path.write_bytes(original)
    def transform(n,b):
     if n!='xl/workbook.xml':return b
     return ('<?xml version="1.0" encoding="'+encoding+'"?><!DOCTYPE workbook [<!ENTITY hidden "injected">]>'+b.decode()).encode(encoding)
    self.rewrite(transform);self.reject('document types')
 def test_duplicate_relationship(self):
  self.rewrite(lambda n,b:b.replace(b'</Relationships>',b'<Relationship Id="rId1" Target="other.xml"/></Relationships>') if n.endswith('.rels') else b);self.reject('Duplicate workbook relationship')
 def test_external_relationship(self):
  self.rewrite(lambda n,b:b.replace(b'Target=',b'TargetMode="External" Target=') if n.endswith('.rels') else b);self.reject('External workbook')
 def test_duplicate_cell(self):
  self.rewrite(lambda n,b:b.replace(b'</ns0:row>',b'<ns0:c r="A1"><ns0:v>999</ns0:v></ns0:c></ns0:row>',1) if n.endswith('sheet1.xml') else b);self.reject('duplicate worksheet cell')
 def test_cell_in_wrong_row(self):
  self.rewrite(lambda n,b:b.replace(b'r="A2"',b'r="A3"') if n.endswith('sheet1.xml') else b);self.reject('does not match')
 def test_duplicate_row(self):
  self.rewrite(lambda n,b:b.replace(b'<ns0:row r="2"',b'<ns0:row r="1"') if n.endswith('sheet1.xml') else b);self.reject('worksheet row')
 def test_negative_shared_string_reference(self):
  # Use an unambiguous shared-string cell regardless of the fixture's first value.
  self.rewrite(lambda n,b:b.replace(b'</ns0:row>',b'<ns0:c r="ZZ1" t="s"><ns0:v>-1</ns0:v></ns0:c></ns0:row>',1) if n.endswith('sheet1.xml') else b);self.reject('shared string index')
 def test_nonfinite_numeric_cell(self):
  self.rewrite(lambda n,b:b.replace(b'</ns0:row>',b'<ns0:c r="ZZ1"><ns0:v>1e999</ns0:v></ns0:c></ns0:row>',1) if n.endswith('sheet1.xml') else b);self.reject('Nonfinite')
 def test_crc_corruption_not_accepted(self):
  # Corrupt an uncompressed XML payload without updating its ZIP CRC.
  raw=self.path.read_bytes();self.path.write_bytes(raw.replace(b'53.33',b'99.99'))
  with self.assertRaises(zipfile.BadZipFile):workbook_cut(self.path,SCOPE)

if __name__=='__main__':unittest.main()
