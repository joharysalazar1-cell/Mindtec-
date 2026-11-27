import json,unittest
from pathlib import Path
import engine,collection_watch,declared_pop_run as run
import test_perfect_store_watch as fixtures

class Tests(unittest.TestCase):
 def setUp(self):
  self.f=fixtures.WatchTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.root=self.f.root;self.runtime=self.root/'pop';self.definition=self.root/'definition.txt';self.definition.write_text('Synthetic owner POP among brand-present stores');self.observation=self.root/'choices.txt';self.observation.write_text('Synthetic brand POP choices')
  self.f.o.poll()
  with engine.Engine(self.f.runtime) as e:
   row=e.db.execute('SELECT * FROM runs').fetchone();sha=json.loads(collection_watch.object_bytes(e,row['snapshot_hash']))['source_sha256']
  self.scope=self.root/'scope.json';self.q={'schema':'mindtec-pop-question-universe/1','version':'synthetic','detailed_workbook_sha256':sha,'forms':{'form':{'mode':'brands','gate_suffix':'tiene_material_marketing','categories_suffix':'categorias_material','category_choices':['bebidas_sin_alcohol','lacteos','detergentes','otros'],'families':{'bebidas_sin_alcohol':{'suffix':'marcas_material_bebidas','choices':['coca_cola','otros']},'lacteos':{'suffix':'marcas_material_lacteos','choices':['pil','otros']}}}},'observations':[{'form':'form','path':str(self.observation),'sha256':engine.sha(self.observation.read_bytes())}]};self.scope.write_text(json.dumps(self.q));self.sha=engine.sha(self.definition.read_bytes())
 def execute(self,target=None):return run.execute(self.f.runtime,target or self.runtime,self.scope,self.definition,self.sha)
 def test_idempotence_and_original_custody(self):
  a=self.execute();b=self.execute();self.assertEqual(a['run_id'],b['run_id'])
  with engine.Engine(self.runtime) as e:
   e.verify();self.assertEqual(e.db.execute('SELECT count(*) FROM runs').fetchone()[0],1);row=e.db.execute('SELECT * FROM runs').fetchone();refs=json.loads(row['rules_json'])['reference_sources']
   for key in ['source_ps_result','source_ps_execution','source_ps_detailed_workbook','source_ps_operational_configuration','implementation','observed_definition','question_observation_1','question_scope']:self.assertIn(key,refs)
 def test_definition_or_observation_tampering_rejects_before_output(self):
  self.definition.write_text('changed')
  with self.assertRaises(ValueError):self.execute()
  self.assertFalse(self.runtime.exists());self.sha=engine.sha(self.definition.read_bytes());self.observation.write_text('changed')
  with self.assertRaises(ValueError):self.execute()
  self.assertFalse(self.runtime.exists())
 def test_missing_form_evidence_and_wrong_cut_rejected(self):
  self.q['observations']=[];self.scope.write_text(json.dumps(self.q))
  with self.assertRaises(ValueError):self.execute()
  self.assertFalse(self.runtime.exists())
 def test_source_corruption_is_not_accepted(self):
  with engine.Engine(self.f.runtime) as e:
   row=e.db.execute('SELECT object_path FROM snapshots LIMIT 1').fetchone();(e.root/row[0]).write_bytes(b'altered')
  with self.assertRaises(ValueError):self.execute()
  self.assertFalse(self.runtime.exists())
 def test_missing_or_overlapping_source_not_created(self):
  with self.assertRaises(ValueError):run.execute(self.root/'missing',self.runtime,self.scope,self.definition,self.sha)
  self.assertFalse((self.root/'missing').exists())
  with self.assertRaises(ValueError):self.execute(self.f.runtime/'child')

if __name__=='__main__':unittest.main()
