import json,unittest
import engine,collection_watch,cold_share_run as run,numeric_distribution_run,cold_share_report as report
import test_perfect_store_watch as fixtures

class ExecutionTests(unittest.TestCase):
 def setUp(self):
  self.fixture=fixtures.WatchTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups);self.root=self.fixture.root;self.source=self.root/'distribution';self.runtime=self.root/'cold'
 def test_custody_idempotent_and_originals_retained(self):
  accepted=self.fixture.o.poll();numeric_distribution_run.execute(self.fixture.runtime,self.source);a=run.execute(self.source,self.runtime);b=run.execute(self.source,self.runtime);self.assertEqual(a['run_id'],b['run_id'])
  with engine.Engine(self.runtime) as e:
   e.verify();self.assertEqual(e.db.execute('SELECT count(*) FROM runs').fetchone()[0],1);r=e.db.execute('SELECT * FROM runs').fetchone();result=json.loads(collection_watch.object_bytes(e,r['snapshot_hash']));rules=json.loads(r['rules_json']);self.assertEqual(result['source_ps_run_id'],accepted['run_id']);self.assertEqual(result['monthly'][0]['state'],'zero_observed_faces');self.assertIn('detailed_workbook',rules['reference_sources']);self.assertIn('admission_manifest',rules['reference_sources']);self.assertIn('source_ps_implementation',rules['reference_sources'])
 def test_missing_and_unaccepted_source_create_no_destination(self):
  with self.assertRaises(ValueError):run.execute(self.root/'missing',self.runtime)
  self.assertFalse((self.root/'missing').exists());self.assertFalse(self.runtime.exists())
  with engine.Engine(self.source):pass
  with self.assertRaises(ValueError):run.execute(self.source,self.runtime)
  self.assertFalse(self.runtime.exists())
 def test_source_destination_cannot_overlap(self):
  for dest in [self.source,self.source/'child',self.root]:
   with self.assertRaises(ValueError):run.execute(self.source,dest)
 def test_corrupt_provenance_rejected_before_writing(self):
  self.fixture.o.poll();numeric_distribution_run.execute(self.fixture.runtime,self.source)
  with engine.Engine(self.source) as e:
   row=e.db.execute('SELECT object_path FROM snapshots LIMIT 1').fetchone();(e.root/row[0]).write_bytes(b'changed')
  with self.assertRaises(ValueError):run.execute(self.source,self.runtime)
  self.assertFalse(self.runtime.exists())

 def test_report_transport_and_exclusive_output_preserve_snapshot(self):
  self.fixture.o.poll();numeric_distribution_run.execute(self.fixture.runtime,self.source);a=run.execute(self.source,self.runtime)
  with engine.Engine(self.runtime) as e:
   original=json.loads(collection_watch.object_bytes(e,a['snapshot']));packed,groups=report.pack(original);self.assertEqual(report.restore(packed,groups),original)
  path=self.root/'report.html';meta=report.export(self.runtime,path,a['run_id']);self.assertEqual(meta['run_id'],a['run_id']);self.assertIn('no equivale a 0 %',path.read_text(encoding='utf-8'))
  with self.assertRaises(FileExistsError):report.export(self.runtime,path)
  with self.assertRaises(ValueError):report.export(self.runtime,self.root/'wrong.html','0'*64)
 def test_scope_evidence_retained_and_alteration_rejected(self):
  self.fixture.o.poll();numeric_distribution_run.execute(self.fixture.runtime,self.source);obs=self.root/'scope.txt';obs.write_text('Observed scope evidence',encoding='utf-8')
  with engine.Engine(self.source) as e:
   row=e.db.execute('SELECT * FROM runs').fetchone();nd=json.loads(collection_watch.object_bytes(e,row['snapshot_hash']));sha=nd['source_sha256']
  rule={'schema':'mindtec-cold-layout/1','version':'synthetic','detailed_workbook_sha256':sha,'forms':{'form':'explicit_zero_bsa_count_means_no_bsa_cold_faces'},'observations':[{'path':str(obs),'form':'form','sha256':engine.sha(obs.read_bytes())}]};path=self.root/'scope.json';path.write_text(json.dumps(rule),encoding='utf-8');run.execute(self.source,self.runtime,path)
  with engine.Engine(self.runtime) as e:
   row=e.db.execute('SELECT * FROM runs').fetchone();self.assertIn('cooler_scope_observation_1',json.loads(row['rules_json'])['reference_sources'])
  obs.write_text('Altered',encoding='utf-8')
  with self.assertRaises(ValueError):run.execute(self.source,self.root/'other',path)
  self.assertFalse((self.root/'other').exists())

if __name__=='__main__':unittest.main()
