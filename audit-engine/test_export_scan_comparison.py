import json,unittest
import engine,export_scan_comparison
import test_scan_compare_watch as fixtures

class ExportTests(unittest.TestCase):
 def setUp(self):
  self.f=fixtures.ObserverTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.output=self.f.root/'export.json'
 def export(self):return export_scan_comparison.export(self.f.source,self.f.runtime,['2026-09','2026-10'],self.output)
 def test_baseline_export_contains_exact_retained_artifacts_and_never_overwrites(self):
  accepted=self.f.o.poll();result=self.export();raw=self.output.read_bytes();pkg=json.loads(raw)
  self.assertEqual(result['local_run_id'],accepted['run_id']);self.assertEqual(result['sha256'],engine.sha(raw));self.assertFalse(result['uploaded'])
  for a in pkg['artifacts'].values():self.assertEqual(engine.sha(a['text']),a['sha256'])
  self.assertFalse(pkg['limits']['local_ledger_included']);self.assertEqual(json.loads(pkg['result_text'])['state'],'baseline_only')
  with self.assertRaises(FileExistsError):self.export()
  self.assertEqual(self.output.read_bytes(),raw)
 def test_changed_cut_exports_both_originals_without_reading_mutable_input(self):
  self.f.o.poll();previous=self.f.input.read_bytes();self.f.data['envios'][1]['revision']='REVISADA';self.f.ingest();current=self.f.input.read_bytes();self.f.o.poll();self.f.input.write_text('not accepted')
  self.export();pkg=json.loads(self.output.read_bytes());self.assertEqual(pkg['artifacts']['previous_scan_source']['text'].encode(),previous);self.assertEqual(pkg['artifacts']['current_scan_source']['text'].encode(),current)
  batch=json.loads(pkg['result_text']);self.assertEqual(batch['monthly']['2026-10']['summary']['changed_records'],1)
 def test_corrupt_custody_or_destination_inside_runtime_rejected(self):
  accepted=self.f.o.poll()
  with self.assertRaises(ValueError):export_scan_comparison.export(self.f.source,self.f.runtime,['2026-09','2026-10'],self.f.runtime/'export.json')
  with engine.Engine(self.f.runtime) as e:
   digest=e.db.execute('SELECT snapshot_hash FROM runs WHERE id=?',(accepted['run_id'],)).fetchone()[0];obj=e.db.execute('SELECT object_path FROM snapshots WHERE hash=?',(digest,)).fetchone()[0]
  (self.f.runtime/obj).write_bytes(b'changed')
  with self.assertRaises(ValueError):self.export()
  self.assertFalse(self.output.exists())

if __name__=='__main__':unittest.main()
