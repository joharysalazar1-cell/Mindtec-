import unittest,copy
import weighted_inputs as w,perfect_store,shelf_share,cold_conversion as cold
from test_cold_conversion import fixture
from test_perfect_store import adapter,CONFIG

class Tests(unittest.TestCase):
 def doors(self,extra=None,overrides=None,scope='all_coolers'):
  a=adapter({'g/hay_enfriadores':'si',**(overrides or {})},{'g/cuantos_enfriadores':1,'rep_enfriador[1]/enfriador_encendido':'si','rep_enfriador[1]/puertas_enfriador':2,**(extra or {})});return w.cooling_doors(a,a.records[0],scope)
 def test_full_operating_inventory_counts_doors(self):self.assertEqual(self.doors()['value'],2)
 def test_partial_positive_operation_does_not_prove_total_doors(self):
  r=self.doors({'g/cuantos_enfriadores':2,'g/cuantos_enfriadores_bsa':1},scope='bsa_subset');self.assertIsNone(r['value']);self.assertEqual(r['known_subtotal_not_total'],2)
 def test_off_equipment_does_not_require_a_door_count(self):self.assertEqual(self.doors({'rep_enfriador[1]/enfriador_encendido':'no','rep_enfriador[1]/puertas_enfriador':''})['value'],0)
 def test_unknown_operation_or_doors_does_not_create_zero(self):
  for k in ['rep_enfriador[1]/enfriador_encendido','rep_enfriador[1]/puertas_enfriador']:
   self.assertIsNone(self.doors({k:''})['value'])
 def test_negative_gate_with_equipment_is_not_zero(self):self.assertIsNone(self.doors(overrides={'g/hay_enfriadores':'no'})['value'])
 def test_explicit_no_equipment_is_zero(self):
  a=adapter({'g/hay_enfriadores':'no'});self.assertEqual(w.cooling_doors(a,a.records[0],'all_coolers')['value'],0)
 def test_bad_door_values_rejected(self):
  for value in [-1,1.5,'2',True]:self.assertIsNone(self.doors({'rep_enfriador[1]/puertas_enfriador':value})['value'])
 def test_company_ranges_and_frequency_preserved_without_midpoints(self):
  a=adapter({}, {'g/empresas_compra':'embol','g/n_empresas_compra':1,'rep_empresa_compra[1]/empresa_actual':'embol','rep_empresa_compra[1]/monto_compra_empresa':'300_1000','rep_empresa_compra[1]/frecuencia_compra_empresa':'dos_semana'});r=w.purchase_declarations(a,a.records[0]);self.assertTrue(r['enumeration_complete']);self.assertIsNone(r['monthly_category_purchase']);self.assertEqual(r['rows'][0]['amount_raw'],'300_1000')
 def test_unmapped_physical_amount_cell_is_preserved_without_guessing_route(self):
  from test_flat_answers import fixture as raw_fixture
  from flat_answers import FlatAnswers
  header='Cuando compras, ¿a cuánto equivale cada compra de productos de ${empresa_label}?[1]'
  book,historical=raw_fixture([header],['300_1000'],[('legacy/unrelated','Other question','x')]);a=FlatAnswers(book,historical);r=w.purchase_declarations(a,a.records[0])
  self.assertEqual(r['original_amount_header_observations'][0]['value'],'300_1000');self.assertIsNone(r['monthly_category_purchase']);self.assertFalse(r['original_amount_header_observations'][0]['historical_route_assigned'])
 def test_missing_company_enumeration_stays_pending(self):
  a=adapter();self.assertFalse(w.purchase_declarations(a,a.records[0])['enumeration_complete'])
 def inputs(self):
  a,c,n,f,q=fixture({'rep_enfriador[1]/puertas_enfriador':2,'g/n_bsa_gaseosas':1,'rep_bsa_gaseosas[1]/marca_act_bsa_gaseosas':'coca_cola','rep_bsa_gaseosas[1]/marca_lbl_bsa_gaseosas':'Coca-Cola','rep_bsa_gaseosas[1]/caras_bsa_gaseosas':10});ps=perfect_store.evaluate(a,c,{'exclusions':[]},CONFIG);s=shelf_share.evaluate(a,c,[('1','2026-09')],ps['eligibility_checks'],ps['answer_evidence'],ps['cells']);s.update(source_ps_run_id='ps-run',source_ps_snapshot_sha256='ps-snapshot');cv=cold.evaluate(a,c,[('1','2026-09')],n,f,q);return a,s,cv
 def test_size_component_is_not_an_official_weight(self):
  a,s,c=self.inputs();before=copy.deepcopy([s,c]);r=w.evaluate(a,s,c);self.assertEqual([s,c],before)
  for row in r['category_stores']:
   self.assertIsNone(row['official_weight']);self.assertEqual(row['observed_size_candidate'],row['category_faces']+8)
   for aid in row['answer_ids']:self.assertTrue(all(cid in r['cells'] for cid in r['answer_evidence'][aid]['cell_ids']))
 def test_incompatible_cut_or_cohort_rejected(self):
  for field in ['source_sha256','source_ps_run_id','source_ps_snapshot_sha256']:
   a,s,c=self.inputs();c[field]='wrong'
   with self.assertRaises(ValueError):w.evaluate(a,s,c)
  a,s,c=self.inputs();s['category_inventories']*=2
  with self.assertRaises(ValueError):w.evaluate(a,s,c)
 def test_altered_cell_rejected(self):
  a,s,c=self.inputs();next(iter(c['cells'].values()))['value']='changed'
  with self.assertRaises(ValueError):w.evaluate(a,s,c)

if __name__=='__main__':unittest.main()
