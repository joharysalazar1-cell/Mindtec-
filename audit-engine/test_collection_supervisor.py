import datetime as dt,json,tempfile,unittest
from pathlib import Path
import supervisor

class SupervisorCollectionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.job={'name':'collection','kind':'collection','interval':30,**{k:str(self.root/(k+'.xlsx' if k in ('source','initial_reference') else k)) for k in ['source','policy','crosswalk','runtime','initial_reference']}}
 def config(self):
  p=self.root/'config.json';p.write_text(json.dumps({'schema':'mindtec-supervisor/1','jobs':[self.job]}));return supervisor.config_file(p)
 def test_explicit_selected_files_are_pinned(self):
  self.config();cmd=supervisor.command(self.job)
  self.assertTrue(cmd[1].endswith('collection_watch.py'));self.assertIn('--crosswalk',cmd);self.assertIn('--initial-reference',cmd)
 def test_nested_input_and_relative_reference_rejected(self):
  self.job['source']=str(Path(self.job['runtime'])/'source.xlsx')
  with self.assertRaises(ValueError):self.config()
  self.job['source']=str(self.root/'source.xlsx');self.job['initial_reference']='relative.xlsx'
  with self.assertRaises(ValueError):self.config()
 def test_too_fast_interval_rejected(self):
  self.job['interval']=1
  with self.assertRaises(ValueError):self.config()
 def test_health_requires_owned_fresh_process_and_custody_flag(self):
  p=Path(self.job['runtime']);p.mkdir();clock=dt.datetime.now(dt.timezone.utc)
  (p/'health.json').write_text(json.dumps({'pid':7,'checked_at':clock.isoformat(),'status':'healthy','custody_verified':True,'network_delivery':False,'run_id':'r'}))
  self.assertEqual(supervisor.health(self.job,8,clock)['status'],'awaiting_owned_health')
  h=supervisor.health(self.job,7,clock);self.assertTrue(h['custody_verified']);self.assertFalse(h['network_delivery'])

if __name__=='__main__':unittest.main()
