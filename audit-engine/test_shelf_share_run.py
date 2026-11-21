import unittest,json
import engine,collection_watch,numeric_distribution_run,shelf_share_run,shelf_share_report
import test_perfect_store_watch as fixtures

class Tests(unittest.TestCase):
 def setUp(self):
  self.f=fixtures.WatchTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.root=self.f.root;self.provenance=self.root/'distribution';self.runtime=self.root/'shelf';self.assertEqual(self.f.o.poll()['status'],'healthy');numeric_distribution_run.execute(self.f.runtime,self.provenance)
 def test_preserves_original_sources_and_deduplicates_same_cut(self):
  a=shelf_share_run.execute(self.provenance,self.runtime);b=shelf_share_run.execute(self.provenance,self.runtime);self.assertEqual(a['run_id'],b['run_id'])
  with engine.Engine(self.runtime) as e:
   self.assertEqual(e.db.execute('SELECT count(*) FROM runs').fetchone()[0],1);run=e.db.execute('SELECT * FROM runs').fetchone();refs=json.loads(run['rules_json'])['reference_sources'];self.assertIn('source_ps_implementation',refs);self.assertIn('detailed_workbook',refs);r=json.loads(collection_watch.object_bytes(e,run['snapshot_hash']));self.assertIsNone(r['monthly'][0]['value']);self.assertEqual(len(json.loads(run['findings_json'])),1)
 def test_does_not_create_missing_provenance_or_use_overlapping_custody(self):
  missing=self.root/'absent'
  with self.assertRaises(ValueError):shelf_share_run.execute(missing,self.runtime)
  self.assertFalse(missing.exists())
  with self.assertRaises(ValueError):shelf_share_run.execute(self.provenance,self.root)
 def test_corrupted_source_cannot_create_a_shelf_result(self):
  with engine.Engine(self.provenance) as e:
   p=e.db.execute('SELECT object_path FROM snapshots LIMIT 1').fetchone();(e.root/p[0]).write_bytes(b'corrupt')
  with self.assertRaises(ValueError):shelf_share_run.execute(self.provenance,self.runtime)
  self.assertFalse((self.runtime/'audit.sqlite').exists())
 def test_report_is_bound_to_exact_execution_and_immutable(self):
  a=shelf_share_run.execute(self.provenance,self.runtime);p=self.root/'shelf.html';meta=shelf_share_report.export(self.runtime,p,a['run_id']);self.assertEqual(meta['run_id'],a['run_id']);self.assertIn('Un subtotal conocido no es un denominador completo',p.read_text(encoding='utf-8'))
  with self.assertRaises(FileExistsError):shelf_share_report.export(self.runtime,p)
  with self.assertRaises(ValueError):shelf_share_report.export(self.runtime,self.root/'bad.html','0'*64)
 def layout_file(self):
  observation=self.root/'layout.txt';observation.write_bytes(b'Synthetic layout observation; not a real platform assertion.');config={'schema':'mindtec-other-face-layouts/1','version':'synthetic','detailed_workbook_sha256':self.f.a['sources']['detailed_workbook']['sha256'],'forms':{'form':{'layout':'direct_parent_faces'}},'observations':[{'path':str(observation),'sha256':engine.sha(observation.read_bytes()),'form':'form'}]};path=self.root/'layout.json';path.write_text(engine.canonical(config),encoding='utf-8');return path,observation
 def test_layout_evidence_and_configuration_retained_by_fingerprint(self):
  path,observation=self.layout_file();a=shelf_share_run.execute(self.provenance,self.runtime,path)
  with engine.Engine(self.runtime) as e:
   run=e.db.execute('SELECT * FROM runs WHERE id=?',(a['run_id'],)).fetchone();refs=json.loads(run['rules_json'])['reference_sources'];self.assertIn('other_layout_configuration',refs);self.assertIn('other_layout_observation_1',refs);envelope=json.loads(collection_watch.object_bytes(e,refs['other_layout_observation_1']));self.assertEqual(envelope['original_sha256'],engine.sha(observation.read_bytes()))
  observation.write_bytes(b'changed')
  with self.assertRaises(ValueError):shelf_share_run.execute(self.provenance,self.runtime,path)
  with engine.Engine(self.runtime) as e:self.assertEqual(e.db.execute('SELECT count(*) FROM runs').fetchone()[0],1)
 def test_layout_for_another_source_does_not_advance_custody(self):
  path,_=self.layout_file();c=json.loads(path.read_bytes());c['detailed_workbook_sha256']='b'*64;path.write_text(engine.canonical(c),encoding='utf-8')
  with self.assertRaises(ValueError):shelf_share_run.execute(self.provenance,self.runtime,path)
  self.assertFalse((self.runtime/'audit.sqlite').exists())

if __name__=='__main__':unittest.main()
