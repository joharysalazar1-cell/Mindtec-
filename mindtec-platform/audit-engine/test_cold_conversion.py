import copy,unittest
import cold_conversion as metric,cold_share,numeric_distribution,perfect_store
from test_perfect_store import adapter,CATALOG,CONFIG

def fixture(extra=None,overrides=None,layout='legacy_global_brand_list',equipment='all_coolers',catalog=None,config=None):
 catalog=copy.deepcopy(catalog or CATALOG);config=copy.deepcopy(config or CONFIG);a=adapter({'g/hay_enfriadores':'si',**(overrides or {})},{'g/cuantos_enfriadores':1,'rep_enfriador[1]/enfriador_encendido':'si','rep_enfriador[1]/tipo_enfriador':'congelador_freezer','g/n_marcas_frias':1,'g/marcas_frias_seleccionadas':'coca_cola','rep_caras_frias[1]/marca_fria_actual':'coca_cola','rep_caras_frias[1]/caras_frias':2,**(extra or {})});ps=perfect_store.evaluate(a,catalog,{'exclusions':[]},config);nd=numeric_distribution.evaluate(ps,catalog,[('1','2026-09')]);cold=cold_share.evaluate(a,catalog,[('1','2026-09')],ps['eligibility_checks'],ps['answer_evidence'],ps['cells'])
 for r in [nd,cold]:r.update(source_ps_run_id='ps-run',source_ps_snapshot_sha256='ps-snapshot')
 q={'schema':'mindtec-cold-conversion-scope/1','version':'synthetic','detailed_workbook_sha256':a.source_sha256,'unit':'brand_within_family','operating_rule':'any_reported_operating_cooler','negative_operating_requires_total_enumeration':True,'forms':{'form':{'equipment_rows_scope':equipment,'cold_layout':layout}}};return a,catalog,nd,cold,q

def run(*args,**kwargs):
 a,c,n,f,q=fixture(*args,**kwargs);return metric.evaluate(a,c,[('1','2026-09')],n,f,q)

class EquipmentTests(unittest.TestCase):
 def test_operating_freezer_counts_without_reusing_ps_vertical_access(self):
  r=run();self.assertEqual(r['equipment'][0]['value'],1);self.assertEqual(r['monthly'][0]['value'],100)
 def test_positive_partial_bsa_inventory_proves_one_operating(self):
  r=run({'g/cuantos_enfriadores':2,'g/cuantos_enfriadores_bsa':1},equipment='bsa_subset');self.assertEqual(r['equipment'][0]['value'],1);self.assertFalse(r['equipment'][0]['total_enumerated'])
 def test_negative_partial_bsa_inventory_does_not_prove_everything_off(self):
  r=run({'g/cuantos_enfriadores':2,'g/cuantos_enfriadores_bsa':1,'rep_enfriador[1]/enfriador_encendido':'no'},equipment='bsa_subset');self.assertIsNone(r['equipment'][0]['value']);self.assertIsNone(r['monthly'][0]['value'])
 def test_zero_bsa_with_unlisted_total_equipment_is_unknown(self):
  a=adapter({'g/hay_enfriadores':'si'},{'g/cuantos_enfriadores':1,'g/cuantos_enfriadores_bsa':0});r=metric.equipment(a,a.records[0],{'equipment_rows_scope':'bsa_subset'});self.assertIsNone(r['value'])
 def test_complete_total_inventory_all_no_excludes_base(self):
  r=run({'rep_enfriador[1]/enfriador_encendido':'no'});self.assertEqual(r['equipment'][0]['value'],0);self.assertEqual(r['monthly'][0]['state'],'no_operating_brand_presence_base');self.assertIsNone(r['monthly'][0]['value']);self.assertIn('cold_count_without_operating_equipment',r['stores'][0]['signals'])
 def test_negative_gate_with_positive_equipment_remains_conflict(self):
  r=run(overrides={'g/hay_enfriadores':'no'});self.assertIsNone(r['equipment'][0]['value']);self.assertIsNone(r['stores'][0]['cold'])
 def test_positive_gate_zero_total_and_count_mismatch_not_accepted(self):
  r=run({'g/cuantos_enfriadores':0});self.assertIsNone(r['equipment'][0]['value']);r=run({'g/cuantos_enfriadores':1,'g/cuantos_enfriadores_bsa':2},equipment='bsa_subset');self.assertIsNone(r['equipment'][0]['value'])
 def test_missing_count_does_not_erase_explicit_positive_operation(self):
  r=run({'g/cuantos_enfriadores':''});self.assertEqual(r['equipment'][0]['value'],1);self.assertIn('equipment_subset_enumeration_unresolved',r['equipment'][0]['signals'])
 def test_explicit_no_equipment_with_no_rows_is_resolved(self):
  a=adapter({'g/hay_enfriadores':'no'});r=metric.equipment(a,a.records[0],{'equipment_rows_scope':'all_coolers'});self.assertEqual(r['value'],0)

class ConversionTests(unittest.TestCase):
 def test_same_brand_in_two_subcategories_counted_once_per_family(self):
  catalog=CATALOG+[dict(CATALOG[0],category='bsa_gaseosas_sin_azucar')];r=run({'g/vende_bsa_gaseosas_sin_azucar':'si','g/marcas_bsa_gaseosas_sin_azucar':'coca_cola'},catalog=catalog);self.assertEqual(len(r['brand_families']),1);self.assertEqual(len(r['stores']),1);self.assertEqual(r['monthly'][0]['denominator'],1);self.assertEqual(len(r['brand_families'][0]['categories_referenced']),2)
 def test_global_legacy_faces_do_not_assign_one_brand_to_two_families(self):
  catalog=[{'category':cat,'brand_code':'delizia','brand':'Delizia'} for cat in ['bsa_jugos','lac_leche_natural']];extra={'g/vende_bsa_jugos':'si','g/marcas_bsa_jugos':'delizia','g/vende_lac_leche_natural':'si','g/marcas_lac_leche_natural':'delizia','g/marcas_frias_seleccionadas':'delizia','rep_caras_frias[1]/marca_fria_actual':'delizia'};r=run(extra,catalog=catalog);self.assertTrue(all(s['value'] is None for s in r['monthly']));self.assertTrue(all('legacy_cold_brand_family_ambiguous' in s['signals'] for s in r['stores']))
 def test_complete_zero_cold_is_real_zero_in_operating_presence_base(self):
  r=run({'rep_caras_frias[1]/caras_frias':0});self.assertEqual(r['monthly'][0]['value'],0);self.assertEqual(r['monthly'][0]['denominator'],1)
 def test_incomplete_cold_enumeration_does_not_create_absence(self):
  r=run({'g/n_marcas_frias':2,'rep_caras_frias[1]/caras_frias':0});self.assertIsNone(r['monthly'][0]['value'])
 def test_positive_cold_face_does_not_prove_equipment_operation(self):
  r=run({'rep_enfriador[1]/enfriador_encendido':''});self.assertEqual(r['stores'][0]['cold'],1);self.assertIsNone(r['stores'][0]['eligible']);self.assertIsNone(r['monthly'][0]['value'])
 def test_missing_brand_presence_does_not_shrink_denominator(self):
  r=run(overrides={'g/marcas_bsa_gaseosas':''});self.assertIsNone(r['stores'][0]['presence']);self.assertEqual(r['monthly'][0]['eligibility_pending'],1)
 def test_absent_brand_not_automatically_made_a_measured_failure(self):
  r=run(overrides={'g/marcas_bsa_gaseosas':'pepsi'});self.assertEqual(r['stores'][0]['state'],'not_in_conversion_base');self.assertIsNone(r['monthly'][0]['value']);self.assertIn('cold_presence_without_declared_brand_presence',r['stores'][0]['signals'])
 def test_direct_category_cold_presence_is_measured_at_family_level(self):
  extra={'g/cuantos_enfriadores_bsa':1,'g/n_frio_bsa_gaseosas':1,'rep_frio_bsa_gaseosas[1]/marca_frio_act_bsa_gaseosas':'coca_cola','rep_frio_bsa_gaseosas[1]/caras_frio_bsa_gaseosas':3};r=run(extra,layout='category_repetitions',equipment='bsa_subset');self.assertEqual(r['monthly'][0]['value'],100)
 def test_duplicate_legacy_brand_identity_is_not_accepted(self):
  r=run({'g/n_marcas_frias':2,'rep_caras_frias[2]/marca_fria_actual':'coca_cola','rep_caras_frias[2]/caras_frias':1});self.assertIsNone(r['stores'][0]['cold'])
 def test_source_cut_execution_and_scope_mismatch_rejected(self):
  for what in ['cut','execution','scope','unit','forms','rows']:
   a,c,n,f,q=fixture()
   if what=='cut':f['source_sha256']='other'
   elif what=='execution':f['source_ps_run_id']='other'
   elif what=='scope':q['detailed_workbook_sha256']='other'
   elif what=='unit':q['unit']='category'
   elif what=='forms':q['forms']={}
   else:f['stores']=[]
   with self.assertRaises(ValueError):metric.evaluate(a,c,[('1','2026-09')],n,f,q)
 def test_corrupt_evidence_and_duplicate_cohort_rejected(self):
  a,c,n,f,q=fixture();next(iter(n['cells'].values()))['value']='changed'
  with self.assertRaises(ValueError):metric.evaluate(a,c,[('1','2026-09')],n,f,q)
  a,c,n,f,q=fixture()
  with self.assertRaises(ValueError):metric.evaluate(a,c,[('1','2026-09'),('1','2026-09')],n,f,q)
 def test_source_arrays_not_mutated_and_all_evidence_resolves(self):
  a,c,n,f,q=fixture();before=copy.deepcopy([c,n,f,q]);r=metric.evaluate(a,c,[('1','2026-09')],n,f,q);self.assertEqual([c,n,f,q],before)
  for row in r['stores']:
   for aid in row['answer_ids']:
    for cid in r['answer_evidence'][aid]['cell_ids']:self.assertIn(cid,r['cells'])
 def test_coca_cola_sponsorship_does_not_remove_pepsi_from_any_equipment_base(self):
  catalog=CATALOG+[{'category':'bsa_gaseosas','brand_code':'pepsi','brand':'Pepsi'}];config=copy.deepcopy(CONFIG);config['company_by_brand']['pepsi']='cbn';extra={'rep_enfriador[1]/tipo_enfriador':'nevera_vertical','rep_enfriador[1]/enfriador_patrocinado':'si','rep_enfriador[1]/marca_enfriador':'Coca-Cola','g/marcas_frias_seleccionadas':'pepsi','rep_caras_frias[1]/marca_fria_actual':'pepsi'};r=run(extra,{'g/marcas_bsa_gaseosas':'pepsi'},catalog=catalog,config=config);self.assertEqual(next(s for s in r['monthly'] if s['brand_code']=='pepsi')['value'],100)
 def test_year_pools_observed_eligible_store_months_and_keeps_pending(self):
  template={'family':'f','brand_code':'c','brand':'B','eligible':True,'id':'x'};rows=[dict(template,month='2026-09',cold=1),dict(template,month='2026-10',cold=0),dict(template,month='2026-10',cold=0)];s=metric.aggregate(rows,'2026','year');self.assertEqual(s['value'],100/3);rows[0]['cold']=None;s=metric.aggregate(rows,'2026','year');self.assertIsNone(s['value']);self.assertEqual(s['minimum'],0);self.assertEqual(s['maximum'],100/3)

if __name__=='__main__':unittest.main()
