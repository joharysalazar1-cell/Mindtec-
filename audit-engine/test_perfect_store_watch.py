import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import engine,perfect_store_watch as watch,perfect_store_admission as admission
from test_flat_answers import fixture
from test_collection_audit import cut,setcell
from test_collection_watch import xlsx
from test_perfect_store import CONFIG

class WatchTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name);self.runtime=self.root/'runtime';self.reports=self.root/'reports';self.path=self.root/'admission.json'
  values={'g/vende_bsa_gaseosas':'si','g/marcas_bsa_gaseosas':'coca_cola','g/hay_enfriadores':'no','g/tiene_material_marketing':'no','g/empresas_compra':'embol','g/n_skus_precio':1,'rep_precio[1]/sku_precio_label':'Required SKU','rep_stock_empresa[1]/empresa_actual_stock':'embol','rep_stock_empresa[1]/hay_quiebre_empresa':'no'}
  import re
  answers=[(r,r.split('/')[-1],v) for r,v in values.items()];self.detail,self.schema=fixture([q+''.join(re.findall(r'\[\d+\]',r)) for r,q,v in answers],list(values.values()),answers)
  self.normal=cut()
  for t in self.normal['tables']:t['rows'][0]['cells'][t['headers'].index('Mes')]='2026-09'
  for col,v in [('Subcategoría (código)','bsa_gaseosas'),('Marca (código)','coca_cola'),('Marca','Coca-Cola')]:setcell(self.normal,'brands',col,v)
  policy={'schema':'mindtec-audit-policy/1','version':'synthetic','max_source_bytes':1000000,'exclusions':[]}
  raws={'detailed_workbook':xlsx(self.detail),'normalized_result_workbook':xlsx(self.normal),'historical_question_schema':engine.canonical(self.schema).encode(),'operational_configuration':engine.canonical(CONFIG).encode(),'policy_file':engine.canonical(policy).encode(),'identity_crosswalk':engine.canonical({'rows':[{'internal_id':'1','kobo_id':'1'}]}).encode()}
  sources={}
  for role,raw in raws.items():
   path=self.root/(role+('.xlsx' if role.endswith('workbook') else '.json'));path.write_bytes(raw);sources[role]={'path':str(path),'sha256':engine.sha(raw)}
  self.a={'schema':'mindtec-perfect-store-admission/1','version':'synthetic-1','label':'Synthetic full September export','sources':sources,**{k:{'2026-09':1} for k in admission.COUNT_FIELDS}};self.save();self.o=self.observer()
 def save(self):self.path.write_text(engine.canonical(self.a),encoding='utf-8')
 def observer(self):return watch.Observer(self.path,self.runtime,self.reports)
 def update(self,role,raw):
  Path(self.a['sources'][role]['path']).write_bytes(raw);self.a['sources'][role]['sha256']=engine.sha(raw);self.save()
 def runs(self):
  with engine.Engine(self.runtime) as e:return e.db.execute('SELECT count(*) FROM runs').fetchone()[0]
 def test_real_workbooks_verified_and_restart_idempotent(self):
  first=self.o.poll();self.assertEqual(first['status'],'healthy');self.assertFalse(first['network_delivery']);self.assertEqual(first['last_accepted']['verification']['store_rows'],1)
  report=Path(first['report_path']);self.assertTrue(report.is_file());self.assertEqual(self.observer().poll()['run_id'],first['run_id']);self.assertEqual(self.runs(),1)
 def test_report_periods_follow_admission_instead_of_fixed_2026_months(self):
  t=self.detail['tables'][0];t['rows'][0]['cells'][t['headers'].index('Fecha visita')]='2027-01-15'
  for t in self.normal['tables']:t['rows'][0]['cells'][t['headers'].index('Mes')]='2027-01'
  for field in admission.COUNT_FIELDS:self.a[field]={'2027-01':1}
  self.a['label']='Synthetic January 2027';self.update('detailed_workbook',xlsx(self.detail));self.update('normalized_result_workbook',xlsx(self.normal));h=self.o.poll();self.assertEqual(h['status'],'healthy');html=Path(h['report_path']).read_text(encoding='utf-8');self.assertIn('Fuentes conservadas · 2027-01',html);self.assertIn('Synthetic January 2027',html);self.assertNotIn('<option value="2026-09">',html);self.assertNotIn('16 de noviembre de 2026',html)
 def test_changed_file_without_admission_is_rejected_and_last_result_retained(self):
  first=self.o.poll();path=Path(self.a['sources']['detailed_workbook']['path']);path.write_bytes(b'partial download');bad=self.o.poll();self.assertEqual(bad['status'],'degraded');self.assertEqual(bad['last_accepted']['run_id'],first['run_id']);self.o.poll();self.assertEqual(self.runs(),1)
  with engine.Engine(self.runtime) as e:
   rejected=[json.loads(r[0]) for r in e.db.execute('SELECT event_json FROM events') if json.loads(r[0])['action']=='perfect_store.observer.rejected'];self.assertEqual(len(rejected),1);self.assertTrue(any((e.root/r[0]).read_bytes()==b'partial download' for r in e.db.execute('SELECT object_path FROM snapshots')))
 def test_explicitly_admitted_new_answer_recalculates_preserving_prior_report(self):
  first=self.o.poll();old=Path(first['report_path']).read_bytes();headers=self.detail['tables'][0]['headers'];self.detail['tables'][0]['rows'][0]['cells'][headers.index('tiene_material_marketing')]='si';self.update('detailed_workbook',xlsx(self.detail));new=self.o.poll()
  self.assertEqual(new['status'],'healthy');self.assertNotEqual(first['run_id'],new['run_id']);self.assertEqual(Path(first['report_path']).read_bytes(),old);self.assertEqual(self.runs(),2)
  with engine.Engine(self.runtime) as e:
   run=e.db.execute('SELECT snapshot_hash FROM runs WHERE id=?',(new['run_id'],)).fetchone();result=engine.load_json_bytes(watch.collection_watch.object_bytes(e,run[0]));self.assertIsNone(result['details'][0]['score'])
 def test_declared_coverage_and_cross_export_month_mismatch_rejected(self):
  self.a['expected_detail_counts']['2026-09']=2;self.save();self.assertEqual(self.o.poll()['status'],'degraded');self.assertEqual(self.runs(),0)
  self.a['expected_detail_counts']['2026-09']=1
  for t in self.normal['tables']:t['rows'][0]['cells'][t['headers'].index('Mes')]='2026-10'
  self.a['expected_normalized_counts']={'2026-10':1};self.update('normalized_result_workbook',xlsx(self.normal));self.assertEqual(self.o.poll()['status'],'degraded');self.assertEqual(self.runs(),0)
 def test_wrong_child_parent_is_not_catalogue_evidence(self):
  setcell(self.normal,'brands','ID envío','999');self.update('normalized_result_workbook',xlsx(self.normal));self.assertEqual(self.o.poll()['status'],'degraded');self.assertEqual(self.runs(),0)
 def test_equal_counts_do_not_hide_different_eligible_visits(self):
  self.detail['tables'][0]['rows'][0]['cells'][0]='99';self.update('detailed_workbook',xlsx(self.detail));h=self.o.poll();self.assertEqual(h['status'],'degraded');self.assertIn('cohorts differ',h['reason']);self.assertEqual(self.runs(),0)
 def test_missing_identity_mapping_does_not_drop_a_visit(self):
  self.update('identity_crosswalk',engine.canonical({'rows':[{'internal_id':'2','kobo_id':'1'}]}).encode());self.assertEqual(self.o.poll()['status'],'degraded');self.assertEqual(self.runs(),0)
 def test_report_restored_from_custody_but_tampering_rejected(self):
  first=self.o.poll();p=Path(first['report_path']);original=p.read_bytes();p.unlink();self.assertEqual(self.o.poll()['status'],'healthy');self.assertEqual(p.read_bytes(),original);p.write_bytes(b'changed');self.assertEqual(self.o.poll()['status'],'degraded');self.assertEqual(self.runs(),1)
 def test_corrupt_custody_not_healthy(self):
  self.o.poll()
  with engine.Engine(self.runtime) as e:
   p=e.db.execute('SELECT object_path FROM snapshots LIMIT 1').fetchone();(e.root/p[0]).write_bytes(b'corrupt')
  h=self.o.poll();self.assertEqual(h['status'],'degraded');self.assertFalse(h['custody_verified']);self.assertTrue(h['failure_history_unverified'])
 def test_runtime_namespace_and_separation(self):
  self.o.poll();other=watch.Observer(self.root/'different.json',self.runtime,self.reports);self.assertEqual(other.poll()['status'],'degraded')
  with self.assertRaises(ValueError):watch.Observer(self.path,self.root,self.reports)
  self.a['sources']['detailed_workbook']['path']=str(self.reports/'input.xlsx');self.save();self.assertEqual(self.o.poll()['status'],'degraded')
 def test_implementation_change_requires_restart(self):
  first=self.o.poll()
  with patch.dict(watch.LOADED,{'perfect_store.py':b'different loaded code'}):h=self.o.poll()
  self.assertEqual(h['status'],'degraded');self.assertEqual(h['last_accepted']['run_id'],first['run_id']);self.assertEqual(self.runs(),1)
 def test_lock_excludes_second_observer(self):
  with watch.supervisor.exclusive(self.runtime/'perfect-store-observer.lock'):
   with self.assertRaises(RuntimeError):watch.watch(self.o,60,1)
 def test_supervisor_binds_admission_reports_health_and_interval(self):
  import supervisor
  job={'kind':'perfect_store','name':'ps','admission':str(self.path),'runtime':str(self.runtime),'report_dir':str(self.reports),'interval':60};path=self.root/'supervisor.json';supervisor.atomic(path,{'schema':'mindtec-supervisor/1','jobs':[job]});self.assertEqual(supervisor.config_file(path)[0]['jobs'],[job]);args=supervisor.command(job);self.assertIn('--admission',args);self.assertIn('--report-dir',args);self.assertTrue(args[1].endswith('perfect_store_watch.py'))
  supervisor.atomic(self.runtime/'health.json',{'pid':123,'checked_at':engine.now(),'status':'healthy','run_id':'test-run','custody_verified':True,'report_path':'test-report','finding_count':2,'network_delivery':False});self.assertEqual(supervisor.health(job,123)['report_path'],'test-report');self.assertEqual(supervisor.health(job,999)['status'],'awaiting_owned_health')
  job['interval']=5;supervisor.atomic(path,{'schema':'mindtec-supervisor/1','jobs':[job]})
  with self.assertRaises(ValueError):supervisor.config_file(path)
 def test_report_directory_cannot_overlap_another_job_custody(self):
  import supervisor
  other={'kind':'scan','name':'scan','runtime':str(self.reports),'source':str(self.root/'scan.json'),'policy':str(self.root/'policy.json')};job={'kind':'perfect_store','name':'ps','admission':str(self.path),'runtime':str(self.runtime),'report_dir':str(self.reports),'interval':60};path=self.root/'supervisor.json';supervisor.atomic(path,{'schema':'mindtec-supervisor/1','jobs':[other,job]})
  with self.assertRaises(ValueError):supervisor.config_file(path)
 def test_report_selects_exact_run_even_if_a_later_run_exists(self):
  first=self.o.poll()
  with engine.Engine(self.runtime) as e:
   run=e.db.execute('SELECT * FROM runs WHERE id=?',(first['run_id'],)).fetchone();rules=json.loads(run['rules_json']);policy=json.loads(run['policy_json']);policy['version']='another-explicit-version';raw=watch.collection_watch.object_bytes(e,run['snapshot_hash']);refs={k:(watch.collection_watch.object_bytes(e,digest),'.xlsx' if k.endswith('workbook') else '.json') for k,digest in rules['reference_sources'].items()};later=e.record_result(raw,policy,rules,json.loads(run['findings_json']),{},refs)
  self.assertNotEqual(later['run_id'],first['run_id']);p=self.root/'selected-report.html';result=watch.perfect_store_report.export(self.runtime,p,first['run_id']);self.assertEqual(result['run_id'],first['run_id'])
  with self.assertRaises(ValueError):watch.perfect_store_report.export(self.runtime,self.root/'missing.html','0'*64)

if __name__=='__main__':unittest.main()
