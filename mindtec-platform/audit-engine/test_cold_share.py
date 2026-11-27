import copy,unittest
import cold_share as cold,perfect_store
from test_perfect_store import adapter,CATALOG,CONFIG

def source(extra=None,overrides=None):
 values={'g/n_frio_bsa_gaseosas':2,'rep_frio_bsa_gaseosas[1]/marca_frio_act_bsa_gaseosas':'coca_cola','rep_frio_bsa_gaseosas[1]/caras_frio_bsa_gaseosas':10,'rep_frio_bsa_gaseosas[2]/marca_frio_act_bsa_gaseosas':'pepsi','rep_frio_bsa_gaseosas[2]/caras_frio_bsa_gaseosas':30};values.update(extra or {});a=adapter({'g/hay_enfriadores':'si',**(overrides or {})},values);ps=perfect_store.evaluate(a,CATALOG,{'exclusions':[]},CONFIG);return a,ps

class Tests(unittest.TestCase):
 def calc(self,a,ps):return cold.evaluate(a,CATALOG,[('1','2026-09')],ps['eligibility_checks'],ps['answer_evidence'],ps['cells'])
 def test_category_denominator_and_unlisted_brand_zero(self):
  a,p=source();r=self.calc(a,p);self.assertEqual((r['monthly'][0]['numerator'],r['monthly'][0]['denominator'],r['monthly'][0]['value']),(10,40,25))
  a,p=source({'rep_frio_bsa_gaseosas[1]/marca_frio_act_bsa_gaseosas':'sprite'});self.assertEqual(self.calc(a,p)['monthly'][0]['value'],0)
 def test_blank_zero_and_no_base_are_distinct(self):
  a,p=source({'rep_frio_bsa_gaseosas[2]/caras_frio_bsa_gaseosas':''});r=self.calc(a,p);self.assertIsNone(r['monthly'][0]['value']);self.assertEqual(r['stores'][0]['known_category_faces_subtotal_not_total'],10)
  a,p=source({'rep_frio_bsa_gaseosas[1]/caras_frio_bsa_gaseosas':0,'rep_frio_bsa_gaseosas[2]/caras_frio_bsa_gaseosas':0});self.assertEqual(self.calc(a,p)['monthly'][0]['state'],'zero_observed_faces')
  a=adapter({'g/vende_bsa_gaseosas':'no','g/marcas_bsa_gaseosas':''});p=perfect_store.evaluate(a,CATALOG,{'exclusions':[]},CONFIG);self.assertEqual(self.calc(a,p)['monthly'][0]['state'],'no_eligible_base')
 def test_global_faces_never_partitioned_by_brand_catalogue(self):
  a=adapter({'g/hay_enfriadores':'si'}, {'g/n_marcas_frias':1,'g/marcas_frias_seleccionadas':'coca_cola','rep_caras_frias[1]/marca_fria_actual':'coca_cola','rep_caras_frias[1]/caras_frias':100});p=perfect_store.evaluate(a,CATALOG,{'exclusions':[]},CONFIG);r=self.calc(a,p);self.assertIsNone(r['monthly'][0]['value']);self.assertIn('legacy_global_cold_faces_not_category_attributed',r['stores'][0]['signals']);self.assertTrue(any(c['value']==100 for c in r['cells'].values()))
 def test_empty_category_count_does_not_fallback_to_legacy(self):
  a,p=source({'g/n_frio_bsa_gaseosas':'','g/n_marcas_frias':2});r=self.calc(a,p);self.assertIsNone(r['monthly'][0]['value']);self.assertIn('cold_brand_count_unresolved',r['stores'][0]['signals']);self.assertNotIn('legacy_global_cold_faces_not_category_attributed',r['stores'][0]['signals'])
 def test_gate_no_requires_no_conflicting_rows_in_any_category(self):
  a,p=source(overrides={'g/hay_enfriadores':'no'});self.assertIn('negative_cooler_gate_with_cold_observations',self.calc(a,p)['stores'][0]['signals'])
  a=adapter(extra={'g/n_frio_bsa_gaseosas':0,'rep_frio_bsa_agua[1]/marca_frio_act_bsa_agua':'vital','rep_frio_bsa_agua[1]/caras_frio_bsa_agua':7});p=perfect_store.evaluate(a,CATALOG,{'exclusions':[]},CONFIG);self.assertIsNone(self.calc(a,p)['monthly'][0]['value'])
 def test_negative_gate_conflicting_equipment_is_not_zero(self):
  a=adapter(extra={'g/cuantos_enfriadores':1});p=perfect_store.evaluate(a,CATALOG,{'exclusions':[]},CONFIG);self.assertIsNone(self.calc(a,p)['monthly'][0]['value'])
 def test_explicit_negative_gate_can_confirm_zero_faces(self):
  a=adapter();p=perfect_store.evaluate(a,CATALOG,{'exclusions':[]},CONFIG);r=self.calc(a,p);self.assertEqual(r['stores'][0]['category_faces'],0);self.assertEqual(r['monthly'][0]['state'],'zero_observed_faces')
 def test_scope_contradiction_retains_original_decision(self):
  a,p=source(overrides={'g/vende_bsa_gaseosas':'no','g/marcas_bsa_gaseosas':''});r=self.calc(a,p);self.assertFalse(r['stores'][0]['source_eligible']);self.assertIsNone(r['stores'][0]['eligible']);self.assertIsNone(r['monthly'][0]['value'])
 def test_enumeration_and_indices_cannot_use_partial_total(self):
  for updates in [{'g/n_frio_bsa_gaseosas':3},{'g/n_frio_bsa_gaseosas':1},{'rep_frio_bsa_gaseosas[2]/marca_frio_act_bsa_gaseosas':'coca_cola'}]:
   a,p=source(updates);self.assertIsNone(self.calc(a,p)['monthly'][0]['value'])
 def test_invalid_counts_never_coerced(self):
  for bad in [-1,0.5,True,'30',float('inf')]:
   if bad==float('inf'):self.assertIsNone(cold.integer({'state':'observed','value':bad}));continue
   a,p=source({'rep_frio_bsa_gaseosas[2]/caras_frio_bsa_gaseosas':bad});self.assertIsNone(self.calc(a,p)['monthly'][0]['value'])
 def test_shelf_faces_and_other_branches_are_not_mixed(self):
  a,p=source({'rep_bsa_gaseosas[1]/caras_bsa_gaseosas':9999});self.assertEqual(self.calc(a,p)['monthly'][0]['denominator'],40)
  a,p=source({'rep_frio_bsa_gaseosas[2]/marca_frio_act_bsa_gaseosas':'otras_marcas'});self.assertIn('cold_other_brand_layout_unresolved',self.calc(a,p)['stores'][0]['signals'])
 def test_annual_pools_faces_and_keeps_missing_month_pending(self):
  base={'id':'x','brand':'B','brand_code':'b','category':'c','eligible':True,'state':'complete','category_signals':[]};rows=[dict(base,month='2026-09',brand_faces=1,category_faces=10),dict(base,month='2026-10',brand_faces=30,category_faces=100)];r=cold.aggregate(rows,'2026','year');self.assertEqual(r['value'],100*31/110);rows[0]['state']='pending';self.assertIsNone(cold.aggregate(rows,'2026','year')['value'])
 def test_evidence_unchanged_and_fingerprints_verified(self):
  a,p=source();before=copy.deepcopy(p);r=self.calc(a,p);self.assertEqual(p,before)
  for aid,answer in r['answer_evidence'].items():
   for cid in answer['cell_ids']:self.assertIn(cid,r['cells'])
  p['answer_evidence'][p['eligibility_checks'][0]['support'][0]]['value']='tampered'
  with self.assertRaises(ValueError):self.calc(a,p)
 def test_bad_cohort_or_catalogue_rejected(self):
  a,p=source()
  with self.assertRaises(ValueError):cold.evaluate(a,CATALOG,[('1','2026-09'),('1','2026-09')],p['eligibility_checks'],p['answer_evidence'],p['cells'])
  with self.assertRaises(ValueError):cold.evaluate(a,CATALOG+[dict(CATALOG[0],brand='Other label')],[('1','2026-09')],p['eligibility_checks'],p['answer_evidence'],p['cells'])

class ScopeTests(unittest.TestCase):
 def inv(self,a,category='bsa_gaseosas',enabled=True):
  rules={'forms':{'form':'explicit_zero_bsa_count_means_no_bsa_cold_faces'}} if enabled else None
  return cold.inventory(a,a.records[0],category,{'eligible':True},rules)
 def test_admitted_zero_bsa_count_supports_zero_without_global_absence(self):
  a=adapter({'g/hay_enfriadores':'si'}, {'g/cuantos_enfriadores':3,'g/cuantos_enfriadores_bsa':0,'g/n_frio_bsa_gaseosas':''})
  r=self.inv(a);self.assertEqual(r['faces'],0);self.assertEqual(r['layout'],'admitted_zero_bsa_coolers');self.assertIsNone(self.inv(a,enabled=False)['faces'])
 def test_zero_bsa_never_applies_to_dairy_or_missing_bsa_count(self):
  a=adapter({'g/hay_enfriadores':'si'}, {'g/cuantos_enfriadores_bsa':0,'g/n_frio_lac_leche_natural':''});self.assertIsNone(self.inv(a,'lac_leche_natural')['faces'])
  a=adapter({'g/hay_enfriadores':'si'}, {'g/cuantos_enfriadores':0,'g/cuantos_enfriadores_bsa':''});self.assertIsNone(self.inv(a)['faces'])
 def test_zero_bsa_with_any_bsa_cold_row_stays_conflicted(self):
  for extra in [{'rep_frio_bsa_agua[1]/marca_frio_act_bsa_agua':'vital'},{'g/n_frio_bsa_agua':1},{'rep_enfriador[1]/enfriador_encendido':'no'}]:
   a=adapter({'g/hay_enfriadores':'si'}, {'g/cuantos_enfriadores_bsa':0,**extra});r=self.inv(a);self.assertIsNone(r['faces']);self.assertIn('zero_bsa_coolers_with_cold_observations',r['signals'])
 def test_scope_rules_source_or_supported_layout_must_match(self):
  a,p=source();rules={'schema':'mindtec-cold-layout/1','version':'test','detailed_workbook_sha256':'wrong','forms':{'form':'explicit_zero_bsa_count_means_no_bsa_cold_faces'}}
  with self.assertRaises(ValueError):cold.evaluate(a,CATALOG,[('1','2026-09')],p['eligibility_checks'],p['answer_evidence'],p['cells'],rules)

if __name__=='__main__':unittest.main()
