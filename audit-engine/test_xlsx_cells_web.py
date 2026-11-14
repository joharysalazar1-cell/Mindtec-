import hashlib,json,pathlib,shutil,subprocess,tempfile,unittest,zipfile
from invoice_adapter import workbook_cut

M='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P='http://schemas.openxmlformats.org/package/2006/relationships'
ROOT=pathlib.Path(__file__).resolve().parent

@unittest.skipUnless(shutil.which('node'),'Node.js required for portable cell checks')
class PortableCellsTests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=pathlib.Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def make(self,rows,*,shared=None,book=None,rels=None,encoding='utf-8',sheet_prefix='',worksheet=None):
  path=self.root/'source.xlsx';sheet=worksheet or '<worksheet xmlns="'+M+'"><sheetData>'+rows+'</sheetData></worksheet>'
  parts={'xl/workbook.xml':book or '<workbook xmlns="'+M+'" xmlns:r="'+R+'"><sheets><sheet name="Ítems de facturas" r:id="items"/></sheets></workbook>',
   'xl/_rels/workbook.xml.rels':rels or '<Relationships xmlns="'+P+'"><Relationship Id="items" Target="worksheets/items.xml"/></Relationships>',
   'xl/worksheets/items.xml':sheet_prefix+sheet}
  if shared is not None:parts['xl/sharedStrings.xml']='<sst xmlns="'+M+'">'+shared+'</sst>'
  with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as z:
   for n,t in parts.items():z.writestr(n,('<?xml version="1.0" encoding="'+encoding+'"?>'+t).encode(encoding))
  return path
 def run_node(self,path,cut):
  dest=self.root/'cut.json';dest.write_text(json.dumps(cut,ensure_ascii=True),encoding='utf-8')
  return subprocess.run(['node',str(ROOT/'verify-xlsx-cells.mjs'),str(path),str(dest)],cwd=ROOT,capture_output=True,text=True,timeout=30)
 def parity(self,path):
  cut=workbook_cut(path,{'fixture':'typed parity'});result=self.run_node(path,cut)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr);return cut,json.loads(result.stdout)
 def rejected(self,path,pattern):
  # A falsified claimed JSON must never turn an invalid workbook into a match.
  claimed={'headers':['H'],'rows':[],'provenance':{'original_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'worksheet':'Ítems de facturas','date_system':'excel_1900','formula_cells_using_cached_values':0}}
  result=self.run_node(path,claimed);self.assertNotEqual(result.returncode,0);self.assertIn(pattern,result.stderr)
 def test_typed_cells_rich_text_blank_cached_formula_and_missing_column(self):
  header='<row r="1">'+''.join('<c r="'+c+'1" t="inlineStr"><is><t>'+c+'</t></is></c>' for c in 'ABCDEFGHI')+'</row>'
  row='<row r="3"><c r="A3" t="s"><v>0</v></c><c r="B3" t="inlineStr"><is><r><t> a &amp; </t></r><r><t>β</t></r></is></c><c r="C3" t="b"><v>1</v></c><c r="D3" t="e"><v>#N/A</v></c><c r="E3"><v>1.25e2</v></c><c r="F3"><f>1+2</f><v>3</v></c><c r="G3"><f>NOW()</f><v/></c><c r="H3" t="d"><v>2026-09-01</v></c></row>'
  cut,report=self.parity(self.make(header+row,shared='<si><r><t>Texto</t></r><r><t> compartido</t></r></si>'))
  self.assertEqual(cut['rows'][0]['cells'],['Texto compartido',' a & β',True,'#N/A',125.0,3,None,'2026-09-01',None]);self.assertEqual(report['archives'][0]['formula_cells_using_cached_values'],2)
 def test_utf16_and_normalized_newlines(self):
  rows='<row r="1"><c r="A1" t="inlineStr"><is><t>H</t></is></c></row><row r="2"><c r="A2" t="inlineStr"><is><t>á\r\nb\rc\n</t></is></c></row>'
  for encoding in ['utf-8','utf-16le','utf-16be']:
   with self.subTest(encoding=encoding):self.parity(self.make(rows,encoding=encoding))
 def test_shared_string_empty_and_empty_inline(self):
  self.parity(self.make('<row r="1"><c r="A1" t="s"><v>0</v></c><c r="B1" t="inlineStr"><is/></c></row>',shared='<si/>'))
 def test_source_digest_mismatch(self):
  path=self.make('<row r="1"><c r="A1"><v>1</v></c></row>');cut=workbook_cut(path,{})
  cut['provenance']['original_sha256']='0'*64;result=self.run_node(path,cut);self.assertNotEqual(result.returncode,0);self.assertIn('digest mismatch',result.stderr)
 def test_changed_value_type_row_and_provenance_fail_comparison(self):
  path=self.make('<row r="1"><c r="A1" t="inlineStr"><is><t>H</t></is></c></row><row r="2"><c r="A2"><v>42</v></c></row>');original=workbook_cut(path,{})
  for mode in ['value','type','row','sheet','formulas']:
   with self.subTest(mode=mode):
    cut=json.loads(json.dumps(original))
    if mode=='value':cut['rows'][0]['cells'][0]=43
    if mode=='type':cut['rows'][0]['cells'][0]='42'
    if mode=='row':cut['rows'][0]['source_row']=3
    if mode=='sheet':cut['provenance']['worksheet']='other'
    if mode=='formulas':cut['provenance']['formula_cells_using_cached_values']=1
    result=self.run_node(path,cut);self.assertNotEqual(result.returncode,0);self.assertIn('mismatch',result.stderr)
 def test_dtd_utf8_and_utf16(self):
  for encoding in ['utf-8','utf-16le','utf-16be']:
   with self.subTest(encoding=encoding):self.rejected(self.make('<row r="1"/>',sheet_prefix='<!DOCTYPE worksheet [<!ENTITY attack "x">]>',encoding=encoding),'DTD')
 def test_duplicate_cell_and_row(self):
  for rows,why in [('<row r="1"><c r="A1"/><c r="A1"/></row>','duplicate cell'),('<row r="1"/><row r="1"/>','unordered row')]:self.rejected(self.make(rows),why)
 def test_bad_address_and_string_reference(self):
  for cells,why in [('<c r="A2"/>','address'),('<c r="XFE1"/>','invalid or duplicate'),('<c r="A1" t="s"><v>-1</v></c>','shared string index')]:self.rejected(self.make('<row r="1">'+cells+'</row>'),why)
 def test_numeric_overflow_and_unsafe_integer(self):
  for token,why in [('1e999','nonfinite'),('9007199254740993','exact JavaScript range')]:self.rejected(self.make('<row r="1"><c r="A1"><v>'+token+'</v></c></row>'),why)
 def test_duplicate_attributes_and_duplicate_values(self):
  self.rejected(self.make('<row r="1"><c r="A1" r="B1"/></row>'),'duplicate XML attribute')
  self.rejected(self.make('<row r="1"><c r="A1"><v>1</v><v>2</v></c></row>'),'duplicate cell value')
 def test_unknown_entities_malformed_xml_and_invalid_characters(self):
  for text in ['&unknown;','&#0;','\x00','<unclosed>']:
   with self.subTest(text=repr(text)):self.rejected(self.make('<row r="1"><c r="A1" t="inlineStr"><is><t>'+text+'</t></is></c></row>'),'XLSX cells:')
 def test_1904_external_relationship_and_multiple_invoice_sheets(self):
  self.rejected(self.make('<row r="1"/>',book='<workbook xmlns="'+M+'"><workbookPr date1904="1"/></workbook>'),'1904')
  self.rejected(self.make('<row r="1"/>',rels='<Relationships xmlns="'+P+'"><Relationship Id="items" Target="https://example.org/a" TargetMode="External"/></Relationships>'),'external')
  self.rejected(self.make('<row r="1"/>',book='<workbook xmlns="'+M+'" xmlns:r="'+R+'"><sheets><sheet name="facturas A" r:id="a"/><sheet name="facturas B" r:id="b"/></sheets></workbook>'),'exactly one')
 def test_vendor_matches_pinned_upstream_source(self):
  module=(ROOT/'vendor/sax-1.6.1.mjs').read_bytes();prefix=b'// Generated by build_xml_vendor.py; upstream source is unchanged below.\nconst exports = {};\n';suffix=b'\nexport const SAXParser = exports.SAXParser;\n'
  self.assertTrue(module.startswith(prefix) and module.endswith(suffix));self.assertEqual(hashlib.sha256(module[len(prefix):-len(suffix)]).hexdigest(),'1cdc1270d987cb0f6ee66dd8efb01c50511aa14d17b6163bbbffb21df8cf1c06')

if __name__=='__main__':unittest.main()
