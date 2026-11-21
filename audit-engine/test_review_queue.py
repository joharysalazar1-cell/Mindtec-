import json,re,tempfile,unittest
from pathlib import Path
import engine,review_queue

class QueueTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.runtime=self.root/'runtime';self.fingerprint=engine.sha('synthetic-finding')
  self.finding={'fingerprint':self.fingerprint,'rule':'synthetic','rule_version':'1','title':'Synthetic','severity':'medium','evidence':{'internal_id':'1','cells':[{'coordinate':'A2','value':'</script>'}]},'explanation':'Synthetic review test'}
  with engine.Engine(self.runtime) as e:self.run=e.record_result(b'{"synthetic":true}',{'exclusions':[]},{'reference_sources':{}},[self.finding]);self.before=e.verify()
 def queue(self,name='queue.json'):
  p=self.root/name;review_queue.export_queue(self.runtime,p);return json.loads(p.read_text()),p
 def decision(self,queue=None,name='decision.json'):
  q=queue or self.queue()[0];d=q['decision_contract']|{'fingerprint':self.fingerprint,'actor':'Synthetic test reviewer','note':'Checked synthetic source cell A2','evidence':'Synthetic original, A2'};p=self.root/name;p.write_text(json.dumps(d));return p,d
 def test_export_is_read_only_and_has_exact_binding(self):
  q,_=self.queue();self.assertEqual(q['run_id'],self.run['run_id']);self.assertEqual(q['ledger_head'],self.before);self.assertTrue(q['items'][0]['requires_review'])
  with engine.Engine(self.runtime) as e:self.assertEqual(e.verify(),self.before)
 def test_append_retains_decision_and_history_without_editing_finding(self):
  p,d=self.decision();r=review_queue.apply_decision(self.runtime,p);self.assertNotEqual(r['ledger_head'],self.before)
  with engine.Engine(self.runtime) as e:
   self.assertEqual(json.loads(e.db.execute('SELECT findings_json FROM runs').fetchone()[0]),[self.finding]);row=e.db.execute('SELECT object_path FROM snapshots WHERE hash=?',(r['decision_sha256'],)).fetchone();self.assertEqual((e.root/row[0]).read_bytes(),p.read_bytes())
  q,_=self.queue('after.json');self.assertEqual(q['items'][0]['latest_review']['status'],'en_revision');self.assertTrue(q['items'][0]['requires_review']);self.assertIn('not_platform_authentication',q['items'][0]['latest_review']['identity_assurance'])
 def test_stale_or_replayed_decision_does_not_append(self):
  p,d=self.decision();review_queue.apply_decision(self.runtime,p)
  with self.assertRaisesRegex(ValueError,'Ledger advanced'):review_queue.apply_decision(self.runtime,p)
  with engine.Engine(self.runtime) as e:self.assertEqual(sum(json.loads(x[0])['action']=='finding.reviewed' for x in e.db.execute('SELECT event_json FROM events')),1)
 def test_wrong_snapshot_fingerprint_and_placeholder_rejected(self):
  q,_=self.queue()
  for field,value in [('snapshot_sha256','0'*64),('fingerprint','0'*64),('actor','REPLACE_WITH_REVIEWER_NAME')]:
   p,d=self.decision(q,name=field+'.json');d[field]=value;p.write_text(json.dumps(d))
   with self.assertRaises(ValueError):review_queue.apply_decision(self.runtime,p)
  with engine.Engine(self.runtime) as e:self.assertEqual(e.verify(),self.before)
 def test_duplicate_json_keys_rejected(self):
  p,d=self.decision();p.write_text(p.read_text()[:-1]+',"actor":"another"}')
  with self.assertRaises(ValueError):review_queue.apply_decision(self.runtime,p)
 def test_decisions_do_not_carry_to_later_runs(self):
  p,d=self.decision();d['status']='dato_confirmado';p.write_text(json.dumps(d));review_queue.apply_decision(self.runtime,p)
  with engine.Engine(self.runtime) as e:e.record_result(b'{"synthetic":2}',{'exclusions':[]},{'reference_sources':{}},[self.finding])
  q,_=self.queue('new-run.json');self.assertIsNone(q['items'][0]['latest_review']);self.assertEqual(q['counts']['resolved_by_declared_review'],0)
 def test_existing_output_and_internal_output_are_not_overwritten(self):
  q,p=self.queue()
  with self.assertRaises(FileExistsError):review_queue.export_queue(self.runtime,p)
  with self.assertRaises(ValueError):review_queue.export_queue(self.runtime,self.runtime/'objects/output.json')
 def test_nonexistent_custody_does_not_create_fake_audit(self):
  p=self.root/'absent'
  with self.assertRaises(ValueError):review_queue.export_queue(p,self.root/'no.json')
  self.assertFalse(p.exists())

if __name__=='__main__':unittest.main()
