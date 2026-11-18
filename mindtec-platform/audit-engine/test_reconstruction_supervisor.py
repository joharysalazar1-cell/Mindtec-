import copy,datetime as dt,json,unittest
from pathlib import Path
import supervisor
import test_reconstruction_cycle as cycle_fixture
import test_perfect_store_watch as ps_fixture
from test_supervisor import Child

class Tests(unittest.TestCase):
 def setUp(self):
  self.c=cycle_fixture.Tests();self.c.setUp();self.addCleanup(self.c.doCleanups);self.p=ps_fixture.WatchTests();self.p.setUp();self.addCleanup(self.p.doCleanups);self.c.q['ps_runtime']=str(self.p.runtime);self.c.save();self.root=self.c.root;self.clock=0;self.children=[]
  self.ps={'name':'ps','kind':'perfect_store','admission':str(self.p.path),'runtime':str(self.p.runtime),'report_dir':str(self.p.reports),'interval':60}
  self.job={'name':'reconstruction','kind':'reconstruction','profile':str(self.c.path),'runtime':self.c.q['runtime'],'ps_runtime':str(self.p.runtime),'interval':60}
 def config(self,jobs=None):
  p=self.root/'supervisor.json';p.write_text(json.dumps({'schema':'mindtec-supervisor/1','jobs':jobs if jobs is not None else [self.ps,self.job]}));return supervisor.config_file(p)
 def spawn(self,*args,**kwargs):
  self.assertNotIn('shell',kwargs);c=Child(100+len(self.children));self.children.append(c);return c
 def ready(self,pid=100):supervisor.atomic(self.p.runtime/'health.json',{'pid':pid,'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'healthy','custody_verified':True})
 def test_profile_and_fixed_script_command(self):
  self.config();args=supervisor.command(self.job);self.assertTrue(args[1].endswith('reconstruction_watch.py'));self.assertIn('--profile',args);self.assertNotIn('--runtime',args);self.assertNotIn('--ps-runtime',args)
 def test_missing_ps_or_mismatched_profile_binding_rejected(self):
  with self.assertRaises(ValueError):self.config([self.job])
  self.job['ps_runtime']=str(self.root/'other')
  with self.assertRaises(ValueError):self.config()
 def test_fast_polling_and_custody_mismatch_rejected(self):
  self.job['interval']=30
  with self.assertRaises(ValueError):self.config()
  self.job['interval']=60;self.job['runtime']=str(self.root/'other')
  with self.assertRaises(ValueError):self.config()
 def test_reports_cannot_overlap_other_supervised_custody(self):
  self.c.q['report_dir']=str(self.p.runtime/'inside');self.c.save()
  with self.assertRaises(ValueError):self.config()
 def test_starts_only_after_owned_ps_acceptance_is_ready(self):
  s=supervisor.Supervisor([self.ps,self.job],self.root/'supervision',spawn=self.spawn,monotonic=lambda:self.clock);self.addCleanup(s.close)
  self.assertEqual(s.tick()[1]['status'],'waiting_for_source');self.assertEqual(len(self.children),1)
  self.ready(999);self.assertEqual(s.tick()[1]['status'],'waiting_for_source');self.assertEqual(len(self.children),1)
  self.ready();s.tick();self.assertEqual(len(self.children),2)
 def test_owned_reconstruction_exit_is_restarted_with_backoff(self):
  s=supervisor.Supervisor([self.ps,self.job],self.root/'supervision',spawn=self.spawn,monotonic=lambda:self.clock);self.addCleanup(s.close);s.tick();self.ready();s.tick();self.children[1].code=17
  h=s.tick()[1];self.assertEqual(h['status'],'backoff');self.clock=5;s.tick();self.assertEqual(len(self.children),3);self.assertEqual(s.children[self.job['name']].pid,102)
 def test_stale_reconstruction_health_never_kills_live_child(self):
  s=supervisor.Supervisor([self.ps,self.job],self.root/'supervision',spawn=self.spawn,monotonic=lambda:self.clock);self.addCleanup(s.close);s.tick();self.ready();s.tick();old=(dt.datetime.now(dt.timezone.utc)-dt.timedelta(hours=1)).isoformat();supervisor.atomic(Path(self.job['runtime'])/'health.json',{'pid':101,'checked_at':old,'status':'healthy'});self.assertEqual(s.tick()[1]['status'],'degraded');self.assertFalse(self.children[1].terminated);self.assertEqual(len(self.children),2)
 def test_health_exposes_scope_and_ownership(self):
  now=dt.datetime.now(dt.timezone.utc);supervisor.atomic(Path(self.job['runtime'])/'health.json',{'pid':101,'checked_at':now.isoformat(),'status':'healthy','custody_verified':True,'network_delivery':False,'completed_stages':8,'report_path':'local.html','state':'verified_unchanged'})
  self.assertEqual(supervisor.health(self.job,100,now)['status'],'awaiting_owned_health');h=supervisor.health(self.job,101,now);self.assertEqual(h['completed_stages'],8);self.assertFalse(h['network_delivery']);self.assertTrue(h['custody_verified'])

if __name__=='__main__':unittest.main()
