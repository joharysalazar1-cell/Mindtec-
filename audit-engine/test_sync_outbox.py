import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import engine,invoice_pipeline,kpi_lineage,sync_outbox,lineage_bundle
from invoice_adapter import workbook_cut
from test_invoice_pipeline import fixture_book
from test_invoices import POLICY as INVOICE_POLICY,SCOPE
from test_engine import POLICY as SCAN_POLICY,snapshot,visit,answer
from supervisor import exclusive

class OutboxTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.invoice=self.root/'invoice';self.scan=self.root/'scan';self.lineage=self.root/'lineage';self.outbox=self.root/'outbox';self.kpi=self.root/'kpi';self.ps=self.root/'ps';self.kpi.mkdir();self.ps.mkdir()
  self.book=self.root/'fixture.xlsx';fixture_book(self.book,53.33);self.cut=workbook_cut(self.book,SCOPE);self.source=self.root/'invoice.json';self.write(self.source,self.cut);self.policy=self.root/'policy.json';self.write(self.policy,INVOICE_POLICY)
  invoice_pipeline.execute(self.source,self.policy,self.invoice,original_workbook=self.book)
  self.scan_source=self.root/'scan.json';self.scan_data=snapshot(visit(respuestas=[answer('cold/faces','0')]));self.write_scan()
  self.write(self.kpi/'resultados_12_KPI.json',[{'id':'kpi','mes':'2026-09','marca':'Fixture','categoria':'Fixture','indicador':'Availability','operativo':{'valor':0,'lineas_factura_relacionadas':['test-invoice|1']}}]);self.write(self.kpi/'fuentes_y_alcance.json',{'sha256_facturas':self.cut['provenance']['original_sha256']})
  self.write(self.ps/'detalle_por_tienda.json',[{'mes':'2026-09','categoria':'Fixture','marca':'Fixture','empresa':'Fixture','id_envio':'test-visit','componentes':[{'componente':'Cold','estado':'measured','valor':0,'peso':1,'fuentes':[{'ruta':'cold/faces','valor':'0'}]}]}]);self.make_lineage()
 def tearDown(self):self.tmp.cleanup()
 def write(self,path,data):path.write_text(engine.canonical(data),encoding='utf-8')
 def write_scan(self):
  self.write(self.scan_source,self.scan_data)
  with engine.Engine(self.scan) as e:self.scan_run=e.ingest(self.scan_source,SCAN_POLICY)
 def make_lineage(self):
  self.write(self.ps/'manifiesto.json',{'fuentes':[{'archivo':'cuestionarios_normalizados_2026-11-13.json','sha256':self.scan_run['snapshot']}]});kpi_lineage.execute(self.invoice,self.scan,self.kpi,self.ps,self.lineage)
 def prepare(self,**extra):return sync_outbox.prepare(self.invoice,self.scan,self.lineage,extra.get('runtime',self.outbox),extra.get('origin','https://audit.example.org'),extra.get('project_id','appgprj_fixture'))
 def accepted(self):
  with engine.Engine(self.outbox) as e:
   r=e.db.execute('SELECT * FROM runs ORDER BY at DESC LIMIT 1').fetchone();source=e.db.execute('SELECT object_path FROM snapshots WHERE hash=?',(r['snapshot_hash'],)).fetchone();return dict(r),json.loads((self.outbox/source[0]).read_bytes())
 def test_coherent_package_exact_sources_code_and_idempotence_without_requests(self):
  with patch('urllib.request.urlopen') as network:
   first=self.prepare();second=self.prepare();network.assert_not_called()
  self.assertEqual(first['run_id'],second['run_id']);self.assertTrue(second['reused']);self.assertEqual(second['state'],'prepared_not_sent')
  r,m=self.accepted();self.assertEqual(m['runs']['scan']['local_run_id'],self.scan_run['run_id']);self.assertEqual(m['target']['origin'],'https://audit.example.org')
  self.assertEqual(m['artifacts']['invoice.reference.current_workbook']['sha256'],engine.sha(self.book.read_bytes()))
  self.assertEqual(m['artifacts']['lineage.reference.perfect_store_details']['sha256'],engine.sha((self.ps/'detalle_por_tienda.json').read_bytes()))
  self.assertEqual(set(json.loads(r['rules_json'])['reference_sources']),set(m['artifacts']))
  with engine.Engine(self.outbox) as e:
   self.assertTrue(e.verify());self.assertEqual(e.db.execute('SELECT count(*) FROM runs').fetchone()[0],1)
   for a in m['artifacts'].values():
    row=e.db.execute('SELECT object_path FROM snapshots WHERE hash=?',(a['sha256'],)).fetchone();self.assertEqual(engine.sha((self.outbox/row[0]).read_bytes()),a['sha256'])
 def test_advanced_scan_waits_for_matching_lineage_preserving_last_package(self):
  first=self.prepare();self.scan_data['envios'][0]['codigoTienda']='updated-store';self.write_scan()
  with self.assertRaisesRegex(ValueError,'Lineage has not accepted'):self.prepare()
  self.assertEqual(self.accepted()[0]['id'],first['run_id'])
  self.make_lineage();second=self.prepare();self.assertNotEqual(second['run_id'],first['run_id']);self.assertFalse(second['reused'])
 def test_changed_source_bytes_are_rejected_without_advancing(self):
  first=self.prepare();(self.scan/'objects'/(self.scan_run['snapshot']+'.json')).write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'integrity'):self.prepare()
  self.assertEqual(self.accepted()[0]['id'],first['run_id'])
 def test_outbox_tampering_is_detected_and_not_overwritten(self):
  first=self.prepare();r,m=self.accepted();hash_=m['artifacts']['invoice.reference.current_workbook']['sha256'];path=self.outbox/'objects'/(hash_+'.xlsx');path.write_bytes(b'changed')
  with self.assertRaisesRegex(ValueError,'integrity'):self.prepare()
  self.assertEqual(path.read_bytes(),b'changed')
 def test_missing_verified_original_blocks_preparation(self):
  # A policy-only change creates another accepted JSON evaluation without
  # supplying an original. That must not become a source-verified package.
  self.write(self.policy,INVOICE_POLICY|{'version':'without-original'});invoice_pipeline.execute(self.source,self.policy,self.invoice);self.make_lineage()
  with self.assertRaisesRegex(ValueError,'original must be verified'):self.prepare()
  self.assertFalse((self.outbox/'audit.sqlite').exists())
 def test_target_and_custody_boundaries(self):
  for origin in ['http://audit.example.org','https://user:secret@audit.example.org','https://audit.example.org/api','https://audit.example.org?token=secret',' https://audit.example.org','https://[::1]']:
   with self.subTest(origin=origin),self.assertRaises(ValueError):self.prepare(origin=origin)
  with self.assertRaises(ValueError):self.prepare(project_id='unknown')
  for path in [self.invoice,self.invoice/'nested',self.root]:
   with self.assertRaisesRegex(ValueError,'separate'):self.prepare(runtime=path)
 def test_destination_is_bound_to_new_package_identity(self):
  first=self.prepare();second=self.prepare(origin='https://other.example.org');self.assertNotEqual(first['run_id'],second['run_id'])
 def test_exclusive_process_lock(self):
  with exclusive(self.outbox/'outbox.lock'):
   with self.assertRaises(RuntimeError):self.prepare()
 def test_projection_uses_accepted_parents_not_mutable_inputs(self):
  expected=engine.sha(engine.canonical(lineage_bundle.build(self.kpi,self.ps)));first=self.prepare();r,m=self.accepted()
  self.assertEqual(m['artifacts']['web.lineage_dependencies']['sha256'],expected)
  self.write(self.kpi/'resultados_12_KPI.json',[]);self.write(self.ps/'detalle_por_tienda.json',[])
  self.assertEqual(self.prepare()['run_id'],first['run_id'])
 def test_later_ledger_note_does_not_break_matching_source_identity(self):
  first=self.prepare()
  with engine.Engine(self.scan) as e:
   e.db.execute('BEGIN IMMEDIATE');e.append('fixture.note',{'note':'Synthetic event after the lineage capture'});e.db.execute('COMMIT')
  second=self.prepare();self.assertNotEqual(first['run_id'],second['run_id']);self.assertEqual(self.accepted()[1]['runs']['scan']['local_run_id'],self.scan_run['run_id'])

if __name__=='__main__':unittest.main()
