import copy,json,sqlite3,tempfile,unittest,concurrent.futures
from unittest.mock import patch
from pathlib import Path
from engine import Engine,canonical,detect,validate_scan,validate_policy,watch

POLICY={'schema':'mindtec-audit-policy/1','version':'1','exclusions':[],'max_source_bytes':100000}
def visit(identifier='test-visit',**extra):
 return {'envioKobo':identifier,'codigoTienda':'test-store','respuestas':[],**extra}
def answer(path,value):return {'ruta':path,'pregunta':path,'valor':value}
def snapshot(*rows):return {'total':len(rows),'envios':list(rows)}

class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.source=self.root/'input.json';self.policy=self.root/'policy.json';self.policy.write_text(canonical(POLICY),encoding='utf-8')
 def tearDown(self):
  self.doCleanups();self.temp.cleanup()
 def engine(self,runtime):
  e=Engine(runtime);self.addCleanup(e.close);return e
 def write(self,data):self.source.write_text(canonical(data),encoding='utf-8')
 def test_explained_semantic_rule_and_ambiguous_answer(self):
  r=visit(respuestas=[answer('cat/vende_bsa_agua','no'),answer('cat/marcas_bsa_agua','example_brand'),answer('rep_caras_frias[1]/marca_fria_actual','example_brand'),answer('rep_caras_frias[1]/caras_frias','0')])
  findings=detect(validate_scan(snapshot(r)),POLICY)
  self.assertEqual({f['rule'] for f in findings},{'category_contradiction','cold_zero_faces'})
  self.assertTrue(all(f['disposition']=='needs_human_review' for f in findings))
  self.assertEqual(next(f for f in findings if f['rule']=='cold_zero_faces')['severity'],'info')
  r['respuestas'].append(answer('cat/vende_bsa_agua','si'))
  findings=detect(snapshot(r),POLICY)
  self.assertEqual({f['rule'] for f in findings},{'conflicting_answer','cold_zero_faces'})
 def test_exclusion_requires_evidence_and_does_not_mask_duplicates(self):
  p=copy.deepcopy(POLICY);p['exclusions']=[{'id':'test-visit','reason':'Approved void','evidence':'test decision'}]
  validate_policy(p)
  self.assertEqual([f['rule'] for f in detect(snapshot(visit(),visit()),p)],['duplicate_visit'])
  del p['exclusions'][0]['evidence']
  with self.assertRaises(ValueError):validate_policy(p)
 def test_trace_versions_and_idempotence(self):
  self.write(snapshot(visit(codigoTienda=None)))
  engine=self.engine(self.root/'runtime');one=engine.ingest(self.source,POLICY);two=engine.ingest(self.source,POLICY)
  self.assertEqual(one['run_id'],two['run_id']);self.assertTrue(two['reused'])
  self.assertEqual(engine.db.execute('SELECT count(*) FROM events').fetchone()[0],1)
  p=POLICY|{'version':'2'};three=engine.ingest(self.source,p)
  self.assertNotEqual(one['run_id'],three['run_id'])
  self.assertEqual(one['findings'],three['findings'])
  self.assertTrue(engine.verify())
  engine.review(one['run_id'],one['findings'][0]['fingerprint'],'en_revision','test-reviewer','Check source identifier','test original')
  with self.assertRaises(ValueError):engine.review(one['run_id'],'unknown','dato_confirmado','reviewer','note','evidence')
  with self.assertRaises(sqlite3.IntegrityError):engine.db.execute("UPDATE events SET hash='changed'")
 def test_corrupted_original_is_detected(self):
  self.write(snapshot(visit()));engine=self.engine(self.root/'runtime');r=engine.ingest(self.source,POLICY)
  (engine.root/'objects'/f"{r['snapshot']}.json").write_text('{}')
  with self.assertRaisesRegex(ValueError,'Snapshot integrity'):engine.verify()
 def test_invalid_snapshot_keeps_prior_and_quarantines_bytes(self):
  self.write(snapshot(visit()));runtime=self.root/'runtime'
  healthy=watch(self.source,self.policy,runtime,1,1)
  self.assertEqual(healthy['status'],'healthy')
  self.source.write_text('{broken',encoding='utf-8')
  degraded=watch(self.source,self.policy,runtime,1,1)
  self.assertEqual(degraded['status'],'degraded')
  self.assertEqual(degraded['last_success']['snapshot'],healthy['last_success']['snapshot'])
  engine=self.engine(runtime);self.assertEqual(engine.db.execute('SELECT count(*) FROM runs').fetchone()[0],1)
  row=engine.db.execute('SELECT event_json FROM events ORDER BY seq DESC').fetchone()
  event=json.loads(row[0]);self.assertEqual(event['action'],'ingestion.failed')
  self.assertEqual((runtime/event['payload']['object_path']).read_text(),'{broken')
  self.write(snapshot(visit('new-test')))
  self.assertEqual(watch(self.source,self.policy,runtime,1,1)['status'],'healthy')
  self.assertEqual(engine.db.execute('SELECT count(*) FROM runs').fetchone()[0],2)
 def test_numbers_and_gps_are_not_fraud_decisions(self):
  r=visit(latitud=95,longitud=0,respuestas=[answer('rep_x/caras_bsa_agua','-1'),answer('rep_x/caras_lac_leche','1.5')])
  self.assertEqual([f['rule'] for f in detect(snapshot(r),POLICY)],['invalid_number','invalid_number','invalid_gps'])
  r.update(latitud=0,longitud=0,respuestas=[])
  self.assertEqual(detect(snapshot(r),POLICY),[])
 def test_strict_export_contract(self):
  with self.assertRaises(ValueError):validate_scan({'total':1,'envios':[]})
  with self.assertRaises(ValueError):validate_scan(snapshot({'envioKobo':True,'respuestas':[]}))
 def test_concurrent_observers_commit_one_run(self):
  self.write(snapshot(visit(codigoTienda=None)));runtime=self.root/'runtime'
  with Engine(runtime):pass
  def ingest(_):
   with Engine(runtime) as e:return e.ingest(self.source,POLICY)
  with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:results=list(pool.map(ingest,range(3)))
  self.assertEqual(len({r['run_id'] for r in results}),1)
  with Engine(runtime) as e:
   self.assertEqual(e.db.execute('SELECT count(*) FROM runs').fetchone()[0],1)
   self.assertEqual(e.db.execute('SELECT count(*) FROM events').fetchone()[0],1)
   self.assertTrue(e.verify())
 def test_changed_result_is_detected_even_if_sqlite_guard_removed(self):
  self.write(snapshot(visit()));engine=self.engine(self.root/'runtime');engine.ingest(self.source,POLICY)
  engine.db.execute('DROP TRIGGER runs_no_update')
  engine.db.execute("UPDATE runs SET findings_json='[{}]'")
  with self.assertRaisesRegex(ValueError,'Run evidence integrity'):engine.verify()
 def test_changed_implementation_is_not_used_under_old_identity(self):
  self.write(snapshot(visit()));engine=self.engine(self.root/'runtime')
  with patch('engine.IMPLEMENTATION_SHA','changed'):
   with self.assertRaisesRegex(RuntimeError,'implementation changed'):engine.ingest(self.source,POLICY)
 def test_report_preserves_escaping_and_never_edits_a_review(self):
  from report import export_report
  r=visit(codigoTienda=None,respuestas=[answer('x/vende_a','no'),answer('x/marcas_a','<test>')])
  self.write(snapshot(r));runtime=self.root/'runtime'
  with Engine(runtime) as e:
   e.ingest(self.source,POLICY);before=e.verify()
  out=self.root/'report.html';export_report(runtime,out)
  import re
  data=json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>',out.read_text(encoding='utf-8'),re.S)[1])
  self.assertEqual(data['findings'][0]['evidence']['observed']['brands'],'<test>')
  self.assertEqual(data['reviews'],{})
  with Engine(runtime) as e:self.assertEqual(e.verify(),before)

if __name__=='__main__':unittest.main()
