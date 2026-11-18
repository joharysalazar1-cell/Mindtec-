import unittest,json
import engine,shelf_share_run,weighted_inputs_run as run,cold_conversion_run
import test_cold_conversion_run as source_fixture

class Tests(unittest.TestCase):
 def setUp(self):
  self.f=source_fixture.ExecutionTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.execute();self.shelf=self.f.root/'shelf';shelf_share_run.execute(self.f.nd,self.shelf);self.target=self.f.root/'weighted'
 def execute(self,target=None):return run.execute(self.shelf,self.f.target,target or self.target,self.f.definition,self.f.sha)
 def test_custody_idempotent_and_no_official_weight_claim(self):
  a=self.execute();b=self.execute();self.assertEqual(a['run_id'],b['run_id']);self.assertFalse(a['summary']['official_dp_calculated'])
  x=cold_conversion_run.capture(self.target,'weighted_input_readiness')
  for key in ['source_shelf','source_conversion','source_ps_result','source_ps_execution','observed_definition','scope_configuration','implementation','detailed_workbook']:self.assertIn(key,x['originals'])
 def test_altered_definition_rejected_before_output(self):
  self.f.definition.write_text('changed')
  with self.assertRaises(ValueError):self.execute()
  self.assertFalse(self.target.exists())
 def test_overlapping_custody_rejected(self):
  for p in [self.shelf,self.f.target,self.f.root]:
   with self.assertRaises(ValueError):self.execute(p)
 def test_corrupt_source_rejected_before_output(self):
  with engine.Engine(self.shelf) as e:
   x=e.db.execute('SELECT object_path FROM snapshots LIMIT 1').fetchone();(e.root/x[0]).write_bytes(b'changed')
  with self.assertRaises(ValueError):self.execute()
  self.assertFalse(self.target.exists())

 def test_purchase_binding_observation_tamper_rejected_before_output(self):
  observation=self.f.root/'alias-evidence.txt';observation.write_text('observed schema');config=self.f.root/'alias.json';config.write_text(json.dumps({'observations':[{'form':'form','path':str(observation),'sha256':engine.sha(observation.read_bytes())}]}));observation.write_text('changed')
  with self.assertRaises(ValueError):run.execute(self.shelf,self.f.target,self.target,self.f.definition,self.f.sha,config)
  self.assertFalse(self.target.exists())
 def test_purchase_binding_wrong_source_rejected_before_output(self):
  obs=self.f.root/'alias.txt';obs.write_text('observed schema');config=self.f.root/'alias.json';config.write_text(json.dumps({'schema':'mindtec-purchase-header-binding/1','version':'test','source_sha256':'wrong','forms':{'form':{'repeat':'rep_empresa_compra','field':'monto_compra_empresa','header_template':'Amount ${empresa_label}?[{index}]'}},'observations':[{'form':'form','path':str(obs),'sha256':engine.sha(obs.read_bytes())}]}))
  with self.assertRaises(ValueError):run.execute(self.shelf,self.f.target,self.target,self.f.definition,self.f.sha,config)
  self.assertFalse(self.target.exists())

if __name__=='__main__':unittest.main()
