import copy,unittest
from kpi_lineage import invoice_links,perfect_store_links
from test_invoices import cut,row,POLICY
from invoice_core import evaluate

class Tests(unittest.TestCase):
 def invoice(self):
  c=cut(row(**{'Total neto':0}));c['provenance']['original_sha256']='book-sha';findings,_=evaluate(c,POLICY,source_hash='source-sha')
  k=[{'id':'test-kpi','mes':'2026-09','marca':'Test','categoria':'Test','indicador':'Fair share','operativo':{'lineas_factura_relacionadas':['test-invoice|1'],'valor':5}}]
  return c,findings,k
 def test_declared_dependency_is_not_a_numeric_impact(self):
  c,f,k=self.invoice();r=invoice_links(k,{'sha256_facturas':'book-sha'},c,f,'source-sha')[0];self.assertEqual(len(r['links']),1);self.assertEqual(r['links'][0]['numeric_impact'],'not_established');self.assertEqual(r['operational_value'],5)
 def test_mismatched_workbook_or_finding_cut_is_rejected(self):
  c,f,k=self.invoice()
  with self.assertRaisesRegex(ValueError,'workbook differs'):invoice_links(k,{'sha256_facturas':'another'},c,f,'source-sha')
  with self.assertRaisesRegex(ValueError,'cut mismatch'):invoice_links(k,{'sha256_facturas':'book-sha'},c,f,'another')
 def test_missing_dependency_is_visible_not_silently_validated(self):
  c,f,k=self.invoice();k[0]['operativo']['lineas_factura_relacionadas']=['missing|1'];r=invoice_links(k,{'sha256_facturas':'book-sha'},c,f,'source-sha')[0];self.assertEqual(r['missing_dependencies'],['missing|1']);self.assertFalse(r['links'])
 def ps(self):
  scan={'envios':[{'envioKobo':'visit','respuestas':[{'ruta':'cold/faces','valor':'0'}]}]};manifest={'fuentes':[{'archivo':'cuestionarios_normalizados_2026-11-13.json','sha256':'scan-sha'}]};details=[{'mes':'2026-09','categoria':'Test','marca':'Test','id_envio':'visit','componentes':[{'componente':'Frío','estado':'medido','valor':0,'peso':1,'fuentes':[{'ruta':'cold/faces','valor':'0'}]}]}];findings=[{'fingerprint':'finding','rule':'cold_zero_faces','severity':'info','evidence':{'record_index':0,'record_id':'visit','paths':['cold/faces']}}];return details,manifest,scan,findings
 def test_exact_path_and_value_link_to_component(self):
  d,m,s,f=self.ps();r=perfect_store_links(d,m,s,'scan-sha',f)[0]['components'][0];self.assertEqual(r['links'][0]['matched_paths'],['cold/faces']);self.assertEqual(r['links'][0]['numeric_impact'],'not_established')
 def test_different_cuts_never_join_on_same_id(self):
  d,m,s,f=self.ps()
  with self.assertRaisesRegex(ValueError,'cuts differ'):perfect_store_links(d,m,s,'other-sha',f)
 def test_conflicting_answers_or_value_mismatch_do_not_create_links(self):
  d,m,s,f=self.ps();s['envios'][0]['respuestas'].append({'ruta':'cold/faces','valor':'1'});r=perfect_store_links(d,m,s,'scan-sha',f)[0]['components'][0];self.assertFalse(r['links']);self.assertEqual(r['unresolved_paths'],['cold/faces'])
  s['envios'][0]['respuestas']=[{'ruta':'cold/faces','valor':'1'}];self.assertFalse(perfect_store_links(d,m,s,'scan-sha',f)[0]['components'][0]['links'])
 def test_duplicate_visit_identity_is_not_arbitrarily_resolved(self):
  d,m,s,f=self.ps();s['envios'].append(copy.deepcopy(s['envios'][0]));r=perfect_store_links(d,m,s,'scan-sha',f)[0];self.assertEqual(r['record_matches'],2);self.assertFalse(r['components'][0]['links'])

if __name__=='__main__':unittest.main()
