import copy,json,tempfile,unittest,base64
from pathlib import Path
from unittest.mock import patch
from contextlib import ExitStack
import engine,reconstruction_cycle as cycle

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.path=self.root/'profile.json';self.q={'schema':'mindtec-reconstruction-cycle/1','version':'synthetic','ps_runtime':str(self.root/'ps'),'runtime':str(self.root/'cycle'),'report_dir':str(self.root/'reports'),'inputs':{}}
  for name in cycle.INPUTS:
   p=self.root/(name+'.json');p.write_text('{}');self.q['inputs'][name]={'path':str(p),'sha256':engine.sha(p.read_bytes())}
  self.save();self.ps={'meta':{'run_id':'ps','snapshot_sha256':'snapshot'},'raw':b'{}','execution':b'{}','policy':{'schema':'mindtec-audit-policy/1','version':'synthetic','max_source_bytes':1000000,'exclusions':[]}}
 def save(self):self.path.write_text(json.dumps(self.q),encoding='utf-8')
 def test_exact_profile_and_external_pinned_inputs(self):
  q,raw,refs=cycle.profile(self.path);self.assertEqual(q,self.q);self.assertEqual(len(refs),11)
 def test_missing_input_bad_hash_and_overlapping_paths_rejected(self):
  original=copy.deepcopy(self.q)
  for what in ['missing','hash','overlap','relative']:
   self.q=copy.deepcopy(original)
   if what=='missing':self.q['inputs'].pop('pop_scope')
   elif what=='hash':self.q['inputs']['pop_scope']['sha256']='0'*64
   elif what=='overlap':self.q['report_dir']=self.q['runtime']
   else:self.q['inputs']['pop_scope']['path']='relative.json'
   self.save()
   with self.assertRaises(ValueError):cycle.profile(self.path)
   self.assertFalse((self.root/'cycle').exists())
 def test_nested_observation_tamper_is_detected(self):
  obs=self.root/'observation.txt';obs.write_text('original');p=Path(self.q['inputs']['pop_scope']['path']);p.write_text(json.dumps({'observations':[{'path':str(obs),'sha256':engine.sha(obs.read_bytes())}]}));self.q['inputs']['pop_scope']['sha256']=engine.sha(p.read_bytes());self.save();cycle.profile(self.path);obs.write_text('changed')
  with self.assertRaises(ValueError):cycle.profile(self.path)
 def test_loaded_code_change_rejected_without_running_stages(self):
  with patch.dict(cycle.LOADED,{'reconstruction_cycle.py':b'changed'}):
   with self.assertRaises(ValueError):cycle.implementation()
 def test_wrong_stage_source_is_rejected(self):
  fake={'result':{'source_ps_run_id':'other','source_ps_snapshot_sha256':'snapshot'}}
  with patch.object(cycle.projection,'captured',return_value=fake):
   with self.assertRaises(ValueError):cycle.stage(self.root,'shelf',self.ps)
 def test_stage_failure_never_accepts_partial_cycle(self):
  with patch.object(cycle.projection,'captured',return_value=self.ps),patch.object(cycle.numeric_distribution_run,'execute'),patch.object(cycle,'stage',return_value={}),patch.object(cycle.shelf_share_run,'execute',side_effect=ValueError('bad scope')):
   with self.assertRaisesRegex(ValueError,'bad scope'):cycle.execute(self.path)
  self.assertFalse((self.root/'cycle/audit.sqlite').exists());self.assertFalse((self.root/'reports').exists())
 def test_ps_change_during_stages_prevents_promotion(self):
  changed=copy.deepcopy(self.ps);changed['meta']['run_id']='new-ps'
  with ExitStack() as stack:
   stack.enter_context(patch.object(cycle.projection,'captured',side_effect=[self.ps,changed]));stack.enter_context(patch.object(cycle,'stage',return_value={}))
   for module in [cycle.numeric_distribution_run,cycle.shelf_share_run,cycle.cold_share_run,cycle.declared_availability_run,cycle.declared_pop_run,cycle.cold_conversion_run,cycle.weighted_inputs_run,cycle.projection]:stack.enter_context(patch.object(module,'execute'))
   with self.assertRaisesRegex(ValueError,'acceptance changed'):cycle.execute(self.path)
  self.assertFalse((self.root/'cycle/audit.sqlite').exists());self.assertFalse((self.root/'reports').exists())
 def test_unchanged_context_reuses_verified_acceptance(self):
  bundle=cycle.implementation();raw=self.path.read_bytes();context=engine.sha(engine.canonical({'source':self.ps['meta'],'profile_sha256':engine.sha(raw),'implementation_sha256':engine.sha(bundle)}));prior={'run_id':'accepted','snapshot_sha256':'manifest','custody_verified':True,'result':{'series':engine.sha(str(self.path.resolve())),'context_sha256':context,'report':{'path':'report'}}}
  with patch.object(cycle.projection,'captured',return_value=self.ps),patch.object(cycle,'verified',return_value=prior),patch.object(cycle.numeric_distribution_run,'execute') as first:
   result=cycle.execute(self.path);self.assertTrue(result['reused']);first.assert_not_called()

 def test_duplicate_cycle_lock_is_rejected(self):
  with cycle.supervisor.exclusive(Path(self.q['runtime'])/'reconstruction-cycle.lock'):
   with self.assertRaises(RuntimeError):cycle.execute(self.path)
 def test_windows_long_custody_path_rejected_before_creation(self):
  if cycle.os.name!='nt':self.skipTest('Windows-specific path guard')
  self.q['runtime']=str(self.root/('x'*140));self.save()
  with self.assertRaisesRegex(ValueError,'too long'):cycle.profile(self.path)
  self.assertFalse(Path(self.q['runtime']).exists())

 def retained(self):
  root=Path(self.q['runtime']);context='c'*64;stages={};refs={};policy={'schema':'mindtec-audit-policy/1','version':'synthetic','max_source_bytes':1000000,'exclusions':[]}
  for name,kind in cycle.KINDS.items():
   path=root/'cycles'/context/name
   with engine.Engine(path) as e:r=e.record_result(b'{}',policy,{'kind':kind,'reference_sources':{}},[])
   stages[name]={'runtime':str(path),'run_id':r['run_id'],'snapshot_sha256':r['snapshot']};refs['stage_'+name]=(b'{}','.json')
  report=self.root/'report.html';report.write_bytes(b'<html>Synthetic</html>');raw=report.read_bytes();refs['report']=(engine.canonical({'sha256':engine.sha(raw),'content':base64.b64encode(raw).decode()}).encode(),'.json');result={'context_sha256':context,'stages':stages,'report':{'path':str(report),'sha256':engine.sha(raw)}}
  with engine.Engine(root) as e:r=e.record_result(engine.canonical(result).encode(),policy,{'kind':'reconstruction_cycle','reference_sources':{k:engine.sha(v[0]) for k,v in refs.items()}},[],references=refs)
  return root,report,stages
 def test_verification_checks_report_bytes(self):
  root,report,stages=self.retained();self.assertTrue(cycle.verified(root)['custody_verified']);report.write_bytes(b'changed')
  with self.assertRaises(ValueError):cycle.verified(root)
 def test_verification_checks_stage_objects(self):
  root,report,stages=self.retained();s=stages['cold'];(Path(s['runtime'])/'objects'/(s['snapshot_sha256']+'.json')).write_bytes(b'changed')
  with self.assertRaises(ValueError):cycle.verified(root)
 def test_missing_stage_is_not_recreated(self):
  root,report,stages=self.retained();db=Path(stages['shelf']['runtime'])/'audit.sqlite';db.rename(db.with_suffix('.backup'))
  with self.assertRaisesRegex(ValueError,'custody missing'):cycle.verified(root)
  self.assertFalse(db.exists())

if __name__=='__main__':unittest.main()
