import json,unittest
from pathlib import Path
import engine,collection_watch,declared_availability_run as run,declared_availability_report as report,numeric_distribution_run
import test_perfect_store_watch as fixtures

class Tests(unittest.TestCase):
 def setUp(self):
  self.f=fixtures.WatchTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.root=self.f.root;self.source=self.root/'numeric';self.runtime=self.root/'availability'
 def prepare(self):self.f.o.poll();return numeric_distribution_run.execute(self.f.runtime,self.source)
 def test_idempotence_and_original_reference_custody(self):
  self.prepare();a=run.execute(self.source,self.runtime);b=run.execute(self.source,self.runtime);self.assertEqual(a['run_id'],b['run_id'])
  with engine.Engine(self.runtime) as e:
   e.verify();self.assertEqual(e.db.execute('SELECT count(*) FROM runs').fetchone()[0],1);row=e.db.execute('SELECT * FROM runs').fetchone();rules=json.loads(row['rules_json']);self.assertIn('source_ps_implementation',rules['reference_sources']);self.assertIn('detailed_workbook',rules['reference_sources']);self.assertIn('operational_configuration',rules['reference_sources'])
 def test_missing_or_overlapping_custody_does_not_write(self):
  with self.assertRaises(ValueError):run.execute(self.root/'missing',self.runtime)
  self.assertFalse((self.root/'missing').exists());self.assertFalse(self.runtime.exists())
  with self.assertRaises(ValueError):run.execute(self.source,self.source/'child')
 def test_corrupt_source_rejected(self):
  self.prepare()
  with engine.Engine(self.source) as e:
   row=e.db.execute('SELECT object_path FROM snapshots LIMIT 1').fetchone();(e.root/row[0]).write_bytes(b'altered')
  with self.assertRaises(ValueError):run.execute(self.source,self.runtime)
  self.assertFalse(self.runtime.exists())
 def test_definition_and_question_scope_evidence_retained_and_pinned(self):
  self.prepare();obs=self.root/'question.txt';obs.write_text('Synthetic offered choice embol',encoding='utf-8');definition=self.root/'definition.txt';definition.write_text('Synthetic company-buyer universe',encoding='utf-8')
  with engine.Engine(self.source) as e:
   row=e.db.execute('SELECT * FROM runs').fetchone();sha=json.loads(collection_watch.object_bytes(e,row['snapshot_hash']))['source_sha256']
  q={'schema':'mindtec-company-question-universe/1','version':'synthetic','detailed_workbook_sha256':sha,'forms':{'form':{'offered_companies':['embol']}},'observations':[{'form':'form','path':str(obs),'sha256':engine.sha(obs.read_bytes())}]};qpath=self.root/'question.json';qpath.write_text(json.dumps(q),encoding='utf-8');a=run.execute(self.source,self.runtime,definition,engine.sha(definition.read_bytes()),qpath)
  with engine.Engine(self.runtime) as e:
   row=e.db.execute('SELECT * FROM runs WHERE id=?',(a['run_id'],)).fetchone();refs=json.loads(row['rules_json'])['reference_sources'];self.assertIn('observed_definition',refs);self.assertIn('question_universe_observation_1',refs)
  obs.write_text('Changed',encoding='utf-8')
  with self.assertRaises(ValueError):run.execute(self.source,self.root/'other',definition,engine.sha(definition.read_bytes()),qpath)
  self.assertFalse((self.root/'other').exists())
 def test_missing_definition_hash_cannot_be_accepted(self):
  self.prepare();obs=self.root/'definition.txt';obs.write_text('Synthetic',encoding='utf-8')
  with self.assertRaises(ValueError):run.execute(self.source,self.runtime,obs)
  self.assertFalse(self.runtime.exists())
 def test_report_exact_run_and_no_overwriting(self):
  self.prepare();a=run.execute(self.source,self.runtime);path=self.root/'report.html';meta=report.export(self.runtime,path,a['run_id']);self.assertEqual(meta['run_id'],a['run_id']);self.assertIn('no certifica disponibilidad',path.read_text(encoding='utf-8'))
  with self.assertRaises(FileExistsError):report.export(self.runtime,path)
  with self.assertRaises(ValueError):report.export(self.runtime,self.root/'wrong.html','0'*64)

if __name__=='__main__':unittest.main()
