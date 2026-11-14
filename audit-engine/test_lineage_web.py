import copy,json,subprocess,tempfile,unittest
from pathlib import Path
from engine import canonical
from invoice_core import evaluate
from test_invoices import cut,row,POLICY
from lineage_bundle import build,unpack
from kpi_lineage import invoice_links,perfect_store_links

def web(b,invoice,scan):
 p=subprocess.run(['node',str(Path(__file__).with_name('test-lineage-web.mjs'))],input=canonical({'bundle':b,'invoice':invoice,'scan':scan}),text=True,encoding='utf-8',capture_output=True,check=True)
 return json.loads(p.stdout)

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();p=Path(self.tmp.name);self.p=p
  kpis=[{'id':'k','mes':'2026-09','marca':'Prueba á','categoria':'Test','indicador':'Fair share','publicado_original':'10%','operativo':{'valor':10,'lineas_factura_relacionadas':['test-invoice|1']}}]
  details=[{'mes':'2026-09','categoria':'Test','marca':'Prueba á','empresa':'Test','id_envio':'visit','componentes':[{'componente':'Frío','estado':'medido','valor':0,'peso':1,'motivo':'Description omitted from projection','fuentes':[{'ruta':'frío/caras','valor':'0','pregunta':'Display label omitted'}]}]}]
  for name,data in {'resultados_12_KPI.json':kpis,'fuentes_y_alcance.json':{'sha256_facturas':'book'},'detalle_por_tienda.json':details,'manifiesto.json':{'fuentes':[{'archivo':'cuestionarios_normalizados_2026-11-13.json','sha256':'scan'}]}}.items():(p/name).write_text(canonical(data),encoding='utf-8')
  self.bundle=build(p,p);source=cut(row(**{'Total neto':0}));source['provenance']['original_sha256']='book';f,_=evaluate(source,POLICY,source_hash='invoice')
  self.invoice={'source':source,'source_sha256':'invoice','findings':f};self.scan={'source':{'envios':[{'envioKobo':'visit','respuestas':[{'ruta':'frío/caras','valor':'0'}]}]},'source_sha256':'scan','findings':[{'fingerprint':'signal','rule':'cold_zero_faces','severity':'info','evidence':{'record_index':0,'record_id':'visit','paths':['frío/caras']}}]}
 def tearDown(self):self.tmp.cleanup()
 def parity(self):
  k,ps=unpack(self.bundle);actual=web(self.bundle,self.invoice,self.scan)
  self.assertEqual(actual['invoice_kpis'],invoice_links(k,self.bundle['kpi_scope'],self.invoice['source'],self.invoice['findings'],'invoice'))
  self.assertEqual(actual['perfect_store'],perfect_store_links(ps,self.bundle['perfect_store_manifest'],self.scan['source'],'scan',self.scan['findings']))
  self.assertFalse(actual['parent_bytes_verified_on_server']);self.assertEqual(actual['numeric_impact'],'not_established');return actual
 def test_projection_and_web_preserve_links_and_limits(self):
  result=self.parity();self.assertEqual(result['summary']['invoice_links'],1);self.assertEqual(result['summary']['perfect_store_links'],1)
  self.assertTrue(self.bundle['parent_files']['perfect_store_details']['sha256']);self.assertNotIn('pregunta',self.bundle['answer_pool'][0])
 def test_mismatched_source_or_workbook_is_rejected(self):
  for target,key in [(self.invoice,'source_sha256'),(self.scan,'source_sha256')]:
   old=target[key];target[key]='other'
   with self.assertRaises(subprocess.CalledProcessError):web(self.bundle,self.invoice,self.scan)
   target[key]=old
  self.invoice['source']['provenance']['original_sha256']='other'
  with self.assertRaises(subprocess.CalledProcessError):web(self.bundle,self.invoice,self.scan)
 def test_ambiguous_answer_never_creates_component_link(self):
  self.scan['source']['envios'][0]['respuestas'].append({'ruta':'frío/caras','valor':'1'});result=self.parity();self.assertEqual(result['summary']['perfect_store_links'],0);self.assertEqual(result['summary']['unresolved_component_paths'],1)
 def test_duplicate_rows_and_invalid_pool_indexes_are_rejected(self):
  for mutate in [lambda b:b['perfect_store'].append(copy.deepcopy(b['perfect_store'][0])),lambda b:b['kpis'].append(copy.deepcopy(b['kpis'][0])),lambda b:b['perfect_store'][0]['components'][0]['answer_refs'].append(-1),lambda b:b['kpis'][0].__setitem__('invoice_ref_set',999)]:
   b=copy.deepcopy(self.bundle);mutate(b)
   with self.assertRaises(subprocess.CalledProcessError):web(b,self.invoice,self.scan)
 def test_missing_dependency_stays_visible(self):
  self.bundle['invoice_ref_sets'][0].append('absent|1');result=self.parity();self.assertEqual(result['summary']['missing_invoice_dependencies'],1)

if __name__=='__main__':unittest.main()
