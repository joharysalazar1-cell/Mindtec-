import datetime as dt,json,subprocess,sys,tempfile,time,unittest
from pathlib import Path
from unittest.mock import patch
from supervisor import Supervisor,health,exclusive,atomic,config_file,command,run
from engine import observer_lock

class Child:
 def __init__(self,pid):self.pid=pid;self.code=None;self.terminated=False
 def poll(self):return self.code
 def terminate(self):self.terminated=True;self.code=-15
 def wait(self,timeout):return self.code

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.clock=0;self.children=[]
  self.job={'name':'scan','kind':'scan','source':str(self.root/'source.json'),'policy':str(self.root/'policy.json'),'runtime':str(self.root/'observer'),'interval':1}
 def tearDown(self):self.tmp.cleanup()
 def spawn(self,*args,**kwargs):
  self.assertIsInstance(args[0],list);self.assertNotIn('shell',kwargs);child=Child(100+len(self.children));self.children.append(child);return child
 def supervisor(self):return Supervisor([self.job],self.root/'supervisor',spawn=self.spawn,monotonic=lambda:self.clock)
 def test_stale_or_borrowed_health_never_restarts_live_child(self):
  s=self.supervisor();s.tick();old=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(hours=1)).isoformat();atomic(Path(self.job['runtime'])/'health.json',{'pid':100,'checked_at':old,'status':'healthy'})
  self.clock=3600;state=s.tick();self.assertEqual(state[0]['status'],'degraded');self.assertEqual(len(self.children),1);self.assertFalse(self.children[0].terminated)
  atomic(Path(self.job['runtime'])/'health.json',{'pid':999,'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'healthy'});self.assertEqual(s.tick()[0]['status'],'awaiting_owned_health');self.assertEqual(len(self.children),1);s.close()
 def test_only_confirmed_exit_triggers_delayed_restart(self):
  s=self.supervisor();s.tick();self.children[0].code=7;self.assertEqual(s.tick()[0]['process'],'exited');self.clock=4;s.tick();self.assertEqual(len(self.children),1);self.clock=5;s.tick();self.assertEqual(len(self.children),2);self.assertEqual(s.tick()[0]['pid'],101);s.close()
  recovered=Supervisor([self.job],self.root/'supervisor',spawn=self.spawn);self.assertNotEqual(recovered.head,'GENESIS')
 def test_tampered_operational_chain_is_rejected(self):
  s=self.supervisor();s.tick();s.close();log=s.log;log.write_text(log.read_text(encoding='utf-8').replace('observer.started','observer.changed'),encoding='utf-8')
  with self.assertRaisesRegex(ValueError,'integrity'):self.supervisor()
 def test_exclusive_locks_reject_duplicates_and_release(self):
  for lock in [lambda:exclusive(self.root/'supervisor.lock'),lambda:observer_lock(self.root/'runtime')]:
   with lock():
    with self.assertRaises(RuntimeError):
     with lock():pass
   with lock():pass
 def test_config_pins_execution_and_requires_absolute_paths(self):
  p=self.root/'config.json';atomic(p,{'schema':'mindtec-supervisor/1','jobs':[self.job]});self.assertEqual(config_file(p)[0]['jobs'][0],self.job);self.assertEqual(command(self.job)[0],sys.executable)
  self.job['source']='relative.json';atomic(p,{'schema':'mindtec-supervisor/1','jobs':[self.job]})
  with self.assertRaisesRegex(ValueError,'Absolute'):config_file(p)
 def test_real_child_exit_and_owned_shutdown(self):
  # Real handles, not merely a fake PID or an old health file.
  s=Supervisor([self.job],self.root/'real',monotonic=lambda:self.clock)
  with patch('supervisor.command',return_value=[sys.executable,'-c','raise SystemExit(17)']):s.tick()
  child=s.children['scan'];self.assertEqual(child.wait(timeout=10),17);self.assertEqual(s.tick()[0]['return_code'],17)
  self.clock=5
  with patch('supervisor.command',return_value=[sys.executable,'-c','import time;time.sleep(60)']):s.tick()
  child=s.children['scan'];self.assertIsNone(child.poll());s.close();self.assertIsNotNone(child.poll())
 def test_lineage_configuration_and_live_health_are_supported(self):
  job={'name':'lineage','kind':'lineage','interval':10,**{k:str(self.root/k) for k in ['invoice_runtime','scan_runtime','kpi_dir','perfect_store_dir','runtime','report']}}
  path=self.root/'lineage-config.json';atomic(path,{'schema':'mindtec-supervisor/1','jobs':[job]});config_file(path);args=command(job)
  self.assertTrue(args[1].endswith('lineage_watch.py'));self.assertIn('--invoice-runtime',args);self.assertIn('--perfect-store-dir',args);self.assertNotIn('--source',args)
  atomic(Path(job['runtime'])/'health.json',{'pid':123,'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'healthy','run_id':'lineage-run'})
  self.assertEqual(health(job,123)['run_id'],'lineage-run')
  job['report']='relative.html';atomic(path,{'schema':'mindtec-supervisor/1','jobs':[job]})
  with self.assertRaisesRegex(ValueError,'Absolute'):config_file(path)
 def test_operational_artifacts_are_archived_and_verified(self):
  s=self.supervisor();reference=s.archive(b'exact configuration bytes','.json');s.event('supervisor.started',{'artifacts':{'configuration':reference}})
  self.supervisor();(s.root/reference['path']).write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'artifact integrity'):self.supervisor()
 def test_explicit_stop_request_suppresses_periodic_recovery(self):
  p=self.root/'config.json';atomic(p,{'schema':'mindtec-supervisor/1','jobs':[self.job]});runtime=self.root/'runtime';runtime.mkdir();(runtime/'stop.request').touch()
  with patch('windows_job.protect_current_process') as protection,patch('supervisor.subprocess.Popen') as spawn:
   run(p,runtime);protection.assert_not_called();spawn.assert_not_called()
  state=json.loads((runtime/'supervisor-health.json').read_bytes());self.assertEqual(state['status'],'stopped');self.assertTrue(state['stop_requested'])

if __name__=='__main__':unittest.main()
