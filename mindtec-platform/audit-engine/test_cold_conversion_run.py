import json, unittest
import engine, numeric_distribution_run, cold_share_run, cold_conversion_run as run
import test_perfect_store_watch as fixtures


class ExecutionTests(unittest.TestCase):
 def setUp(self):
  self.f=fixtures.WatchTests();self.f.setUp();self.addCleanup(self.f.doCleanups)
  self.root=self.f.root;self.nd=self.root/'nd';self.cold=self.root/'cold';self.target=self.root/'conversion'
  self.f.o.poll();numeric_distribution_run.execute(self.f.runtime,self.nd);cold_share_run.execute(self.nd,self.cold)
  source=run.capture(self.nd,'declared_numeric_distribution')['result']
  self.definition=self.root/'definition.txt';self.definition.write_text('Synthetic any-operating equipment conversion')
  self.observation=self.root/'observation.txt';self.observation.write_text('Synthetic total equipment form')
  self.scope=self.root/'scope.json'
  self.q={'schema':'mindtec-cold-conversion-scope/1','version':'synthetic','detailed_workbook_sha256':source['source_sha256'],'unit':'brand_within_family','operating_rule':'any_reported_operating_cooler','negative_operating_requires_total_enumeration':True,'forms':{'form':{'equipment_rows_scope':'all_coolers','cold_layout':'legacy_global_brand_list'}},'observations':[{'form':'form','path':str(self.observation),'sha256':engine.sha(self.observation.read_bytes())}]}
  self.scope.write_text(json.dumps(self.q));self.sha=engine.sha(self.definition.read_bytes())
 def execute(self,target=None):
  return run.execute(self.nd,self.cold,target or self.target,self.scope,self.definition,self.sha)
 def test_idempotence_and_retained_provenance(self):
  a=self.execute();b=self.execute();self.assertEqual(a['run_id'],b['run_id'])
  x=run.capture(self.target,'declared_cold_conversion');self.assertEqual(x['meta']['snapshot_sha256'],a['snapshot_sha256'])
  for name in ['source_distribution','source_cold','source_ps_result','source_ps_execution','detailed_workbook','implementation','scope_configuration','scope_observation_1','observed_definition']:
   self.assertIn(name,x['originals'])
  with engine.Engine(self.target) as e:self.assertEqual(e.db.execute('SELECT count(*) FROM runs').fetchone()[0],1)
 def test_altered_definition_or_observation_rejected_before_output(self):
  self.definition.write_text('changed')
  with self.assertRaises(ValueError):self.execute()
  self.assertFalse(self.target.exists());self.sha=engine.sha(self.definition.read_bytes());self.observation.write_text('changed')
  with self.assertRaises(ValueError):self.execute()
  self.assertFalse(self.target.exists())
 def test_form_evidence_and_cut_required(self):
  for key,value in [('observations',[]),('detailed_workbook_sha256','wrong')]:
   q=dict(self.q);q[key]=value;self.scope.write_text(json.dumps(q))
   with self.assertRaises(ValueError):self.execute()
   self.assertFalse(self.target.exists())
 def test_corrupt_source_rejected_before_output(self):
  with engine.Engine(self.cold) as e:
   row=e.db.execute('SELECT object_path FROM snapshots LIMIT 1').fetchone();(e.root/row[0]).write_bytes(b'changed')
  with self.assertRaises(ValueError):self.execute()
  self.assertFalse(self.target.exists())
 def test_missing_source_and_overlapping_output_rejected(self):
  for target in [self.nd,self.nd/'child',self.cold,self.root]:
   with self.assertRaises(ValueError):self.execute(target)
  with self.assertRaises(ValueError):run.execute(self.root/'missing',self.cold,self.target,self.scope,self.definition,self.sha)
  self.assertFalse((self.root/'missing').exists());self.assertFalse(self.target.exists())


if __name__=='__main__':unittest.main()
