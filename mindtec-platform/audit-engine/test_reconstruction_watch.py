import copy,tempfile,json,unittest
from pathlib import Path
from unittest.mock import patch,Mock
import engine,reconstruction_watch as watch,reconstruction_cycle as cycle
import test_reconstruction_cycle as fixture

class Tests(unittest.TestCase):
 def setUp(self):
  self.f=fixture.Tests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.observer=watch.Observer(self.f.path);self.prior={'run_id':'accepted','snapshot_sha256':'manifest','custody_verified':True,'result':{'series':self.observer.series,'context_sha256':'ctx','report':{'path':'report','sha256':'hash'},'stages':{'one':{}}}}
 def test_healthy_unchanged_cycle_and_restart_recover_prior(self):
  accepted={'run_id':'accepted','reused':True,'report':{'path':'report'}}
  with patch.object(cycle,'verified',return_value=self.prior),patch.object(cycle,'execute',return_value=accepted):
   h=self.observer.poll();self.assertEqual(h['status'],'healthy');self.assertEqual(h['state'],'verified_unchanged');self.assertTrue(h['custody_verified']);self.assertFalse(h['network_delivery']);h=watch.Observer(self.f.path).poll();self.assertEqual(h['run_id'],'accepted')
 def test_bad_new_rule_retains_last_good_and_deduplicates_rejection(self):
  with patch.object(cycle,'verified',return_value=self.prior),patch.object(cycle,'execute',side_effect=ValueError('new rule incompatible')):
   a=self.observer.poll();b=self.observer.poll()
  self.assertEqual(a['status'],'degraded');self.assertEqual(b['last_accepted']['run_id'],'accepted');self.assertFalse(b['custody_verified'])
  with engine.Engine(self.observer.runtime) as e:e.verify();self.assertEqual(e.db.execute('SELECT count(*) FROM events').fetchone()[0],1)
 def test_scope_change_cannot_switch_observer_custody(self):
  self.f.q['runtime']=str(self.f.root/'other');self.f.save()
  with patch.object(cycle,'verified',return_value=self.prior),patch.object(cycle,'execute') as execute:
   h=self.observer.poll();self.assertEqual(h['status'],'degraded');execute.assert_not_called()
  self.assertFalse((self.f.root/'other').exists())
 def test_no_source_acceptance_is_not_a_zero_result(self):
  with patch.object(cycle,'verified',return_value=None),patch.object(cycle,'execute',side_effect=ValueError('source absent')):
   h=self.observer.poll();self.assertEqual(h['state'],'no_cycle_accepted');self.assertIsNone(h['last_accepted']);self.assertFalse(h['custody_verified'])
 def test_interval_and_duplicate_observer_lock(self):
  for interval in [True,0,30,3601]:
   with self.assertRaises(ValueError):watch.watch(self.observer,interval,1)
  with watch.supervisor.exclusive(self.observer.runtime/'reconstruction-observer.lock'):
   with self.assertRaises(RuntimeError):watch.watch(self.observer,60,1)

 def test_bounded_watch_marks_process_stopped_not_continuously_healthy(self):
  with patch.object(self.observer,'poll',return_value={'status':'healthy','state':'verified_unchanged','last_accepted':None}):
   h=watch.watch(self.observer,60,1)
  self.assertEqual(h['status'],'stopped');self.assertEqual(h['last_poll_status'],'healthy');self.assertFalse(h['observer_running']);saved=json.loads((self.observer.runtime/'health.json').read_text());self.assertEqual(saved['status'],'stopped')

if __name__=='__main__':unittest.main()
