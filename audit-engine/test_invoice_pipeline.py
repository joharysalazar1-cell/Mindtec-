import copy,json,tempfile,unittest,zipfile,xml.etree.ElementTree as E,base64
from pathlib import Path
from engine import Engine,canonical
from invoice_adapter import workbook_cut
from invoice_pipeline import execute
from test_invoices import HEADERS,POLICY,SCOPE,row

NS='http://schemas.openxmlformats.org/spreadsheetml/2006/main'
def fixture_book(path,amount):
 root=E.Element('{'+NS+'}worksheet');data=E.SubElement(root,'{'+NS+'}sheetData')
 for rn,values in [(1,HEADERS),(2,row(**{'Total neto':amount})['cells'])]:
  r=E.SubElement(data,'{'+NS+'}row',r=str(rn))
  for i,v in enumerate(values):
   c=E.SubElement(r,'{'+NS+'}c',r=chr(65+i)+str(rn))
   if v is None:continue
   if isinstance(v,str):c.set('t','inlineStr');E.SubElement(E.SubElement(c,'{'+NS+'}is'),'{'+NS+'}t').text=v
   else:E.SubElement(c,'{'+NS+'}v').text=str(v)
 with zipfile.ZipFile(path,'w') as z:
  z.writestr('xl/workbook.xml','<workbook xmlns="'+NS+'" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Ítems de facturas" sheetId="1" r:id="rId1"/></sheets></workbook>')
  z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Target="worksheets/sheet1.xml"/></Relationships>')
  z.writestr('xl/worksheets/sheet1.xml',E.tostring(root))

class Tests(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
 def tearDown(self):self.tmp.cleanup()
 def prepare(self,name,amount):
  book=self.root/(name+'.xlsx');fixture_book(book,amount);cut=workbook_cut(book,SCOPE);source=self.root/(name+'.json');source.write_text(canonical(cut),encoding='utf-8');return book,source,cut
 def test_original_and_reference_are_verified_and_archived(self):
  a,pa,_=self.prepare('previous',53.33);b,pb,_=self.prepare('current',54.33);policy=self.root/'policy.json';policy.write_text(canonical(POLICY),encoding='utf-8');runtime=self.root/'runtime'
  result=execute(pb,policy,runtime,pa,b,a);again=execute(pb,policy,runtime,pa,b,a)
  self.assertEqual(result['run_id'],again['run_id']);self.assertTrue(again['reused'])
  self.assertEqual([f['rule'] for f in result['findings']],['invoice_value_change'])
  with Engine(runtime) as engine:
   self.assertEqual(engine.db.execute('SELECT count(*) FROM snapshots').fetchone()[0],5)
   self.assertEqual(engine.db.execute('SELECT count(*) FROM runs').fetchone()[0],1)
   self.assertTrue(engine.verify());record=engine.db.execute('SELECT rules_json FROM runs').fetchone()[0]
   self.assertTrue(json.loads(record)['source_workbook_verified'])
   bundle_hash=json.loads(record)['reference_sources']['implementation_bundle'];bundle=json.loads((runtime/'objects'/(bundle_hash+'.json')).read_text(encoding='utf-8'))
   import invoice_pipeline,hashlib
   code=base64.b64decode(bundle['files']['invoice_pipeline.py']['content']);self.assertEqual(code,Path(invoice_pipeline.__file__).read_bytes());self.assertEqual(hashlib.sha256(code).hexdigest(),bundle['files']['invoice_pipeline.py']['sha256'])
   old_hash=json.loads(record)['reference_sources']['previous_workbook'];stored=runtime/'objects'/(old_hash+'.xlsx');self.assertEqual(stored.read_bytes(),a.read_bytes())
 def test_mismatched_original_never_becomes_a_run(self):
  a,source,cut=self.prepare('source',53.33);cut['rows'][0]['cells'][HEADERS.index('Total neto')]=0;source.write_text(canonical(cut),encoding='utf-8');policy=self.root/'policy.json';policy.write_text(canonical(POLICY),encoding='utf-8')
  with self.assertRaisesRegex(ValueError,'cells differ'):execute(source,policy,self.root/'runtime',original_workbook=a)
  self.assertFalse((self.root/'runtime').exists())
 def test_reference_object_mutation_is_detected(self):
  a,pa,_=self.prepare('previous',53.33);b,pb,_=self.prepare('current',54.33);policy=self.root/'policy.json';policy.write_text(canonical(POLICY),encoding='utf-8');runtime=self.root/'runtime';execute(pb,policy,runtime,pa,b,a)
  with Engine(runtime) as engine:
   original=next((runtime/'objects').glob('*.xlsx'));original.write_bytes(b'changed')
   with self.assertRaisesRegex(ValueError,'Snapshot integrity'):engine.verify()

if __name__=='__main__':unittest.main()
