import copy,json,tempfile,unittest
from pathlib import Path
import engine,scan_compare_watch,supervisor
from test_engine import POLICY
from test_scan_compare import row,cut

class ObserverTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name);self.source=self.root/'scan';self.runtime=self.root/'comparison';self.input=self.root/'input.json';self.data=cut(row(),row('2','2026-10'));self.ingest();self.o=self.observer()
 def observer(self,months=None):return scan_compare_watch.Observer(self.source,self.runtime,months or ['2026-09','2026-10'])
 def ingest(self,policy=None):
  self.input.write_text(engine.canonical(self.data),encoding='utf-8')
  with engine.Engine(self.source) as e:return e.ingest(self.input,policy or POLICY)
 def count(self):
  with engine.Engine(self.runtime) as e:return e.db.execute('SELECT count(*) FROM runs').fetchone()[0]
 def result(self,run_id):
  with engine.Engine(self.runtime) as e:
   row=e.db.execute('SELECT snapshot_hash FROM runs WHERE id=?',(run_id,)).fetchone();return engine.load_json_bytes(scan_compare_watch.object_bytes(e,row[0]))
 def test_baseline_has_no_invented_comparison_and_unchanged_restart_reuses_it(self):
  first=self.o.poll();self.assertEqual(first['state'],'baseline_only');result=self.result(first['run_id']);self.assertIsNone(result['combined']);self.assertEqual(result['monthly'],{});self.assertEqual(result['baseline_counts'],{'2026-09':1,'2026-10':1})
  self.assertEqual(self.o.poll()['run_id'],first['run_id']);self.assertEqual(self.observer().poll()['run_id'],first['run_id']);self.assertEqual(self.count(),1)
 def test_new_cut_creates_bound_monthly_and_combined_views(self):
  baseline=self.o.poll();self.data['envios'][1]['revision']='REVISADA';accepted=self.ingest();result=self.o.poll();self.assertEqual(result['state'],'comparison_available');self.assertNotEqual(result['run_id'],baseline['run_id']);batch=self.result(result['run_id']);self.assertEqual(batch['current_source_sha256'],accepted['snapshot']);self.assertEqual(batch['monthly']['2026-09']['summary']['changed_records'],0);self.assertEqual(batch['monthly']['2026-10']['summary']['changed_records'],1);self.assertEqual(batch['combined']['summary']['changed_records'],1)
  self.assertEqual(self.observer().poll()['run_id'],result['run_id']);self.assertEqual(self.count(),2)
 def test_policy_or_code_only_source_acceptance_is_not_a_data_change(self):
  baseline=self.o.poll();other=self.ingest(POLICY|{'version':'policy-2'})
  result=self.o.poll();self.assertEqual(result['run_id'],baseline['run_id']);self.assertEqual(result['observed_scan_run_id'],other['run_id']);self.assertEqual(self.count(),1)
 def test_incomplete_month_cut_retains_previous_baseline_then_recovers(self):
  baseline=self.o.poll();complete=copy.deepcopy(self.data);self.data=cut(self.data['envios'][0]);self.ingest();bad=self.o.poll();self.assertEqual(bad['status'],'degraded');self.assertEqual(bad['last_accepted']['run_id'],baseline['run_id']);self.assertEqual(self.count(),1)
  self.o.poll()
  with engine.Engine(self.runtime) as e:self.assertEqual(sum(json.loads(r[0])['action']=='scan.comparison.rejected' for r in e.db.execute('SELECT event_json FROM events')),1)
  self.data=complete;self.data['envios'][0]['revision']='new';self.ingest();good=self.o.poll();self.assertEqual(good['state'],'comparison_available');batch=self.result(good['run_id']);self.assertEqual(batch['previous_source_sha256'],baseline['last_accepted']['source_snapshot'])
 def test_mutable_inbox_is_not_used_until_scan_accepts_it(self):
  baseline=self.o.poll();self.input.write_text('invalid pending input');self.assertEqual(self.o.poll()['run_id'],baseline['run_id']);self.assertEqual(self.count(),1)
 def test_source_and_output_corruption_degrade_without_false_freshness(self):
  first=self.o.poll()
  with engine.Engine(self.source) as e:
   digest=e.db.execute('SELECT snapshot_hash FROM runs ORDER BY at DESC LIMIT 1').fetchone()[0];obj=e.db.execute('SELECT object_path FROM snapshots WHERE hash=?',(digest,)).fetchone()[0]
  path=self.source/obj;raw=path.read_bytes();path.write_bytes(b'altered');self.assertEqual(self.o.poll()['status'],'degraded');path.write_bytes(raw)
  with engine.Engine(self.runtime) as e:
   digest=e.db.execute('SELECT snapshot_hash FROM runs WHERE id=?',(first['run_id'],)).fetchone()[0];obj=e.db.execute('SELECT object_path FROM snapshots WHERE hash=?',(digest,)).fetchone()[0]
  (self.runtime/obj).write_bytes(b'altered');bad=self.o.poll();self.assertEqual(bad['status'],'degraded');self.assertFalse(bad['comparison_custody_verified']);self.assertTrue(bad['failure_history_unverified'])
 def test_changed_scope_or_overlapping_runtime_rejected(self):
  self.o.poll();self.assertEqual(self.observer(['2026-09']).poll()['status'],'degraded')
  with self.assertRaises(ValueError):scan_compare_watch.Observer(self.source,self.source/'nested',['2026-09'])
 def test_exclusive_watcher_lock(self):
  with supervisor.exclusive(self.runtime/'scan-comparison.lock'):
   with self.assertRaises(RuntimeError):scan_compare_watch.watch(self.o,10,1)
 def jobs(self):
  return [{'name':'scan','kind':'scan','runtime':str(self.source),'source':str(self.input),'policy':str(self.root/'policy.json'),'interval':10},{'name':'comparison','kind':'scan_comparison','scan_runtime':str(self.source),'runtime':str(self.runtime),'months':['2026-09','2026-10'],'interval':30}]
 def config(self,jobs):
  path=self.root/'supervisor.json';path.write_text(engine.canonical({'schema':'mindtec-supervisor/1','jobs':jobs}),encoding='utf-8');return supervisor.config_file(path)
 def test_supervisor_binding_and_fixed_script(self):
  jobs=self.jobs();self.config(jobs);args=supervisor.command(jobs[1]);self.assertTrue(args[1].endswith('scan_compare_watch.py'));self.assertIn('--months',args)
  with self.assertRaises(ValueError):self.config(jobs[1:])
  jobs[1]['months']=['2026-09','2026-09']
  with self.assertRaises(ValueError):self.config(jobs)
 def test_supervisor_health_distinguishes_baseline_from_comparison(self):
  result=self.o.poll();state=supervisor.health(self.jobs()[1],result['pid']);self.assertEqual(state['state'],'baseline_only');self.assertTrue(state['comparison_custody_verified'])

if __name__=='__main__':unittest.main()
