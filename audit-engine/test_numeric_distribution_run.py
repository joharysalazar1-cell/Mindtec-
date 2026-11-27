import json,unittest
import engine,collection_watch,numeric_distribution_run as run,numeric_distribution_report as report
import test_perfect_store_watch as fixtures

class ExecutionTests(unittest.TestCase):
 def setUp(self):
  self.fixture=fixtures.WatchTests();self.fixture.setUp();self.addCleanup(self.fixture.doCleanups);self.root=self.fixture.root;self.source=self.fixture.runtime;self.runtime=self.root/'distribution-runtime'
 def test_verified_source_result_reused_and_all_inputs_retained(self):
  first=self.fixture.o.poll();self.assertEqual(first['status'],'healthy');a=run.execute(self.source,self.runtime);b=run.execute(self.source,self.runtime);self.assertEqual(a['run_id'],b['run_id'])
  with engine.Engine(self.runtime) as e:
   self.assertEqual(e.db.execute('SELECT count(*) FROM runs').fetchone()[0],1);accepted=e.db.execute('SELECT * FROM runs').fetchone();data=json.loads(collection_watch.object_bytes(e,accepted['snapshot_hash']));rules=json.loads(accepted['rules_json']);self.assertEqual(data['source_ps_run_id'],first['run_id']);self.assertEqual(data['monthly'][0]['value'],100);self.assertIn('source_ps_detailed_workbook',rules['reference_sources']);self.assertIn('source_ps_admission_manifest',rules['reference_sources']);self.assertIn('source_ps_implementation',rules['reference_sources'])
 def test_no_unaccepted_source_or_new_empty_source_database(self):
  missing=self.root/'missing'
  with self.assertRaises(ValueError):run.execute(missing,self.runtime)
  self.assertFalse(missing.exists())
  with engine.Engine(self.source):pass
  with self.assertRaises(ValueError):run.execute(self.source,self.runtime)
  self.assertFalse((self.runtime/'audit.sqlite').exists())
 def test_bad_original_custody_does_not_become_new_distribution(self):
  self.fixture.o.poll()
  with engine.Engine(self.source) as e:
   p=e.db.execute('SELECT object_path FROM snapshots LIMIT 1').fetchone();(e.root/p[0]).write_bytes(b'corrupt')
  with self.assertRaises(ValueError):run.execute(self.source,self.runtime)
  self.assertFalse((self.runtime/'audit.sqlite').exists())
 def test_report_links_exact_run_and_does_not_overwrite(self):
  self.fixture.o.poll();a=run.execute(self.source,self.runtime);path=self.root/'distribution.html';meta=report.export(self.runtime,path,a['run_id']);self.assertEqual(meta['run_id'],a['run_id']);self.assertIn('no son intervalos de confianza',path.read_text(encoding='utf-8'))
  with self.assertRaises(FileExistsError):report.export(self.runtime,path)
  with self.assertRaises(ValueError):report.export(self.runtime,self.root/'wrong.html','0'*64)
 def test_source_and_target_custody_remain_separate(self):
  with self.assertRaises(ValueError):run.execute(self.source,self.source/'child')
  with self.assertRaises(ValueError):run.execute(self.source,self.root)

if __name__=='__main__':unittest.main()
