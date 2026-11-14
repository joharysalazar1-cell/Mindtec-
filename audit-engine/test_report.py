import json,re,tempfile,unittest
from pathlib import Path
from engine import Engine,canonical
from invoice_pipeline import execute
from report import export_report
from test_invoices import HEADERS,POLICY,SCOPE,row
class ReportTests(unittest.TestCase):
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
