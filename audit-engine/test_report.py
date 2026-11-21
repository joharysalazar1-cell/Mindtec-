import json,re,tempfile,unittest
from pathlib import Path
from engine import Engine,canonical
from invoice_pipeline import execute
from report import export_report
from test_invoices import HEADERS,POLICY,SCOPE,row
class ReportTests(unittest.TestCase):
 def collection(self,root):
  from collection_watch import Observer
  from test_collection_watch import xlsx
  from test_collection_audit import cut,setcell
  data=cut();setcell(data,'brands','Caras en góndola',None)
  source=root/'current.xlsx';source.write_bytes(xlsx(data));policy=root/'policy.json';policy.write_text(canonical({'schema':'mindtec-audit-policy/1','version':'1','exclusions':[]}));cross=root/'cross.json';cross.write_text(canonical({'rows':[{'internal_id':'1','kobo_id':'101'}]}))
  observer=Observer(source,policy,cross,root/'runtime');h=observer.poll();self.assertEqual(h['status'],'healthy');return observer,source
 def test_collection_cells_come_from_retained_original_not_mutable_inbox(self):
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);observer,source=self.collection(root);source.write_bytes(b'new incomplete input');output=root/'review.html';export_report(root/'runtime',output);text=output.read_text(encoding='utf-8');data=json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>',text,re.S)[1]);refs=list(data['collection_evidence']['cells_by_fingerprint'].values())[0]
   self.assertEqual(refs[0]['coordinate'],'H2');self.assertIsNone(refs[0]['value']);self.assertEqual(refs[0]['internal_id'],'1');self.assertIn('recordIdentity(f.evidence)',text);self.assertIn('Celdas cotejadas con el XLSX conservado',text)
 def test_semantically_wrong_cell_evidence_rejected_even_with_valid_ledger_hashes(self):
  from report import collection_evidence
  with tempfile.TemporaryDirectory() as directory:
   root=Path(directory);observer,source=self.collection(root);prior=observer.prior();findings=json.loads(json.dumps(prior['result']['findings']));findings[0]['evidence']['cells'][0]['coordinate']='A99'
   with Engine(root/'runtime') as e:
    with self.assertRaisesRegex(ValueError,'differs'):collection_evidence(e,prior['rules'],findings)
 def test_immutable_original_rows_and_hostile_text(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory);policy=p/'policy.json';policy.write_text(canonical(POLICY),encoding='utf-8')
   for name,amount in [('old',53),('new',54)]:
    r=row(**{'Total neto':amount});r['cells'][HEADERS.index('Sticker')]='</script><script>alert(1)</script>'
    (p/(name+'.json')).write_text(canonical({'schema':'mindtec-invoice-cut/1','scope':SCOPE,'headers':HEADERS,'rows':[r]}),encoding='utf-8')
   result=execute(p/'new.json',policy,p/'runtime',p/'old.json');(p/'new.json').write_text('{}')
   output=p/'report.html';export_report(p/'runtime',output);text=output.read_text(encoding='utf-8')
   data=json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>',text,re.S)[1])
   self.assertEqual(len(data['invoice_evidence']),2)
   amounts={record['Total neto'] for source in data['invoice_evidence'].values() for record in source['rows'].values()}
   self.assertEqual(amounts,{53,54});self.assertNotIn('</script><script>alert(1)',text)
   self.assertIn('sourceRows(f.evidence)',text);self.assertIn('change(f.evidence)',text)
   with Engine(p/'runtime') as e:
    source=e.db.execute('SELECT object_path FROM snapshots WHERE hash=?',(result['snapshot'],)).fetchone()[0];(e.root/source).write_text('{}')
   with self.assertRaisesRegex(ValueError,'integrity'):export_report(p/'runtime',output)
