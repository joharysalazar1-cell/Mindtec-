import copy,unittest
import declared_pop as pop,perfect_store
from test_perfect_store import adapter,CATALOG,CONFIG

def inputs(extra=None,overrides=None,config=None):
 config=copy.deepcopy(config or CONFIG);config['company_by_brand'].update(pepsi='cbn',pil='pil_andina');config['company_aliases'].update(cbn='cbn',pil='pil_andina')
 a=adapter({'g/tiene_material_marketing':'si',**(overrides or {})},{'g/categorias_material':'bebidas_sin_alcohol','g/marcas_material_bebidas':'coca_cola',**(extra or {})});ps=perfect_store.evaluate(a,CATALOG,{'exclusions':[]},config)
 q={'schema':'mindtec-pop-question-universe/1','version':'synthetic','detailed_workbook_sha256':a.source_sha256,'forms':{'form':{'mode':'brands','gate_suffix':'tiene_material_marketing','categories_suffix':'categorias_material','category_choices':['bebidas_sin_alcohol','lacteos','detergentes','otros'],'families':{'bebidas_sin_alcohol':{'suffix':'marcas_material_bebidas','choices':['coca_cola','pepsi','otros']},'lacteos':{'suffix':'marcas_material_lacteos','choices':['pil','otros']}}}}}
 return a,ps,config,q

def evaluate(extra=None,overrides=None,config=None):
 a,ps,c,q=inputs(extra,overrides,config);return pop.evaluate(a,CATALOG,[('1','2026-09')],ps,c,q)

class Tests(unittest.TestCase):
 def test_positive_company_pop_over_brand_presence(self):
  r=evaluate();self.assertEqual(r['monthly'][0]['value'],100);self.assertEqual(r['monthly'][0]['denominator'],1);self.assertEqual(r['stores'][0]['company'],'embol')
 def test_another_brand_same_owner_is_a_positive(self):
  config=copy.deepcopy(CONFIG);config['company_by_brand']['fanta']='embol';a,ps,c,q=inputs({'g/marcas_material_bebidas':'fanta'},config=config);q['forms']['form']['families']['bebidas_sin_alcohol']['choices'].append('fanta');r=pop.evaluate(a,CATALOG,[('1','2026-09')],ps,c,q);self.assertEqual(r['stores'][0]['pop'],1)
 def test_fully_observed_other_owner_is_negative(self):
  r=evaluate({'g/marcas_material_bebidas':'pepsi'});self.assertEqual(r['stores'][0]['pop'],0);self.assertEqual(r['monthly'][0]['value'],0)
 def test_other_brand_cannot_confirm_absence_but_does_not_erase_positive(self):
  self.assertIsNone(evaluate({'g/marcas_material_bebidas':'pepsi otros'})['stores'][0]['pop']);self.assertEqual(evaluate({'g/marcas_material_bebidas':'coca_cola otros'})['stores'][0]['pop'],1)
 def test_unhomologated_offered_brand_prevents_negative(self):
  a,ps,c,q=inputs({'g/marcas_material_bebidas':'mystery'});q['forms']['form']['families']['bebidas_sin_alcohol']['choices'].append('mystery');r=pop.evaluate(a,CATALOG,[('1','2026-09')],ps,c,q);self.assertIsNone(r['stores'][0]['pop'])
 def test_unoffered_choice_invalidates_positive(self):
  r=evaluate({'g/marcas_material_bebidas':'coca_cola invented'});self.assertIsNone(r['stores'][0]['pop']);self.assertIn('pop_choice_outside_admitted_universe_or_duplicate',r['stores'][0]['signals'])
 def test_missing_selected_family_list_is_not_negative(self):
  self.assertIsNone(evaluate({'g/marcas_material_bebidas':''})['monthly'][0]['value'])
 def test_negative_gate_requires_no_descendant_values(self):
  self.assertIsNone(evaluate(overrides={'g/tiene_material_marketing':'no'})['stores'][0]['pop'])
  r=evaluate({'g/categorias_material':'','g/marcas_material_bebidas':''},{'g/tiene_material_marketing':'no'});self.assertEqual(r['stores'][0]['pop'],0)
 def test_negative_gate_with_photo_is_pending(self):
  r=evaluate({'g/categorias_material':'','g/marcas_material_bebidas':'','info_pdv/cuerpo_pdv/cuerpo_valido/registro_material_marketing/grupo_material/foto_material_marketing_1':'photo.jpg'},{'g/tiene_material_marketing':'no'});self.assertIsNone(r['stores'][0]['pop'])
 def test_missing_gate_is_pending_even_with_brand_list(self):
  self.assertIsNone(evaluate(overrides={'g/tiene_material_marketing':''})['stores'][0]['pop'])
 def test_inactive_family_with_material_conflicts(self):
  r=evaluate({'g/categorias_material':'lacteos','g/marcas_material_lacteos':'pil'});self.assertIsNone(r['stores'][0]['pop']);self.assertIn('inactive_pop_family_with_observations',r['inventories'][0]['scope_signals'])
 def test_other_category_or_text_does_not_become_homologated_brand(self):
  for extra in [{'g/categorias_material':'bebidas_sin_alcohol otros'},{'g/material_otros_detalle':'Coca-Cola poster'}]:
   r=evaluate({'g/marcas_material_bebidas':'pepsi',**extra});self.assertIsNone(r['stores'][0]['pop'])
 def test_no_brand_presence_has_no_percentage_not_zero(self):
  r=evaluate(overrides={'g/marcas_bsa_gaseosas':'pepsi'});self.assertEqual(r['monthly'][0]['state'],'no_brand_presence_base');self.assertIsNone(r['monthly'][0]['value']);self.assertEqual(r['stores'][0]['state'],'not_in_brand_presence_base')
 def test_pending_presence_is_not_removed_from_base(self):
  r=evaluate(overrides={'g/marcas_bsa_gaseosas':''});self.assertEqual(r['monthly'][0]['state'],'pending_observations');self.assertEqual(r['monthly'][0]['base_pending_store_months'],1)
 def test_company_not_in_choices_cannot_be_negative_in_active_family(self):
  a,ps,c,q=inputs({'g/marcas_material_bebidas':'pepsi'});q['forms']['form']['families']['bebidas_sin_alcohol']['choices'].remove('coca_cola');r=pop.evaluate(a,CATALOG,[('1','2026-09')],ps,c,q);self.assertIsNone(r['stores'][0]['pop'])
 def test_explicit_other_family_can_rule_out_material_for_known_family(self):
  r=evaluate({'g/categorias_material':'lacteos','g/marcas_material_bebidas':'','g/marcas_material_lacteos':'pil'});self.assertEqual(r['stores'][0]['pop'],0)
 def test_duplicate_choice_or_category_is_not_silently_deduplicated(self):
  for extra in [{'g/marcas_material_bebidas':'coca_cola coca_cola'},{'g/categorias_material':'bebidas_sin_alcohol bebidas_sin_alcohol'}]:self.assertIsNone(evaluate(extra)['stores'][0]['pop'])
 def test_bad_source_or_form_configuration_rejected(self):
  for change in ['source','form','version','mode']:
   a,ps,c,q=inputs()
   if change=='source':q['detailed_workbook_sha256']='other'
   elif change=='form':q['forms']['other']=q['forms'].pop('form')
   elif change=='version':c['version']='other'
   else:q['forms']['form']['mode']='companies'
   with self.assertRaises(ValueError):pop.evaluate(a,CATALOG,[('1','2026-09')],ps,c,q)
 def test_original_cells_and_answers_resolve_and_inputs_unchanged(self):
  a,ps,c,q=inputs();before=copy.deepcopy([ps,c,q]);r=pop.evaluate(a,CATALOG,[('1','2026-09')],ps,c,q);self.assertEqual([ps,c,q],before)
  for s in r['stores']:
   for aid in s['answer_ids']:
    for cid in r['answer_evidence'][aid]['cell_ids']:self.assertIn(cid,r['cells'])
 def test_annual_pools_brand_present_visits_and_retains_unknown_months(self):
  template={'id':'x','category':'cat','brand_code':'brand','brand':'Brand','company':'c','eligible':True,'presence':1};rows=[dict(template,month='2026-09',pop=1),dict(template,month='2026-10',pop=0),dict(template,month='2026-10',pop=0)];r=pop.aggregate(rows,'2026','year');self.assertEqual(r['value'],100/3);rows[0]['pop']=None;self.assertIsNone(pop.aggregate(rows,'2026','year')['value'])
 def test_missing_data_bounds_are_not_averaged_or_claimed_exact(self):
  template={'id':'x','category':'cat','brand_code':'brand','brand':'Brand','company':'c','eligible':True,'presence':1};rows=[dict(template,month='2026-09',pop=1),dict(template,month='2026-10',pop=None),dict(template,month='2026-10',pop=0)];r=pop.aggregate(rows,'2026','year');self.assertIsNone(r['value']);self.assertEqual(r['minimum'],100/3);self.assertEqual(r['maximum'],200/3);rows.append(dict(template,month='2026-10',presence=None,pop=None));r=pop.aggregate(rows,'2026','year');self.assertEqual(r['minimum'],25);self.assertEqual(r['maximum'],75)
 def test_user_business_rule_accepts_unselected_company_as_real_zero(self):
  a,ps,c,q=inputs({'g/marcas_material_bebidas':'pepsi otros'});q['forms']['form']['families']['bebidas_sin_alcohol']['choices'].remove('coca_cola');q.update(unselected_owner_policy='confirmed_absence_in_answered_pop_section',absence_rule_evidence={'sha256':'a'*64});r=pop.evaluate(a,CATALOG,[('1','2026-09')],ps,c,q);self.assertEqual(r['stores'][0]['pop'],0);self.assertEqual(r['monthly'][0]['value'],0);self.assertEqual(r['company_rows'][r['stores'][0]['company_row_index']]['reason'],'confirmed_absence_by_user_rule_in_answered_section')
 def test_user_rule_does_not_turn_missing_list_or_contradiction_into_zero(self):
  for extra,overrides in [({'g/marcas_material_bebidas':''},{}),({}, {'g/tiene_material_marketing':'no'})]:
   a,ps,c,q=inputs(extra,overrides);q.update(unselected_owner_policy='confirmed_absence_in_answered_pop_section',absence_rule_evidence={'sha256':'a'*64});r=pop.evaluate(a,CATALOG,[('1','2026-09')],ps,c,q);self.assertIsNone(r['stores'][0]['pop'])
 def test_user_rule_requires_explicit_decision_reference(self):
  a,ps,c,q=inputs();q['unselected_owner_policy']='confirmed_absence_in_answered_pop_section'
  with self.assertRaises(ValueError):pop.evaluate(a,CATALOG,[('1','2026-09')],ps,c,q)
 def test_user_confirmed_zero_is_not_mislabeled_as_blocking_finding(self):
  a,ps,c,q=inputs({'g/marcas_material_bebidas':'pepsi otros'});q.update(unselected_owner_policy='confirmed_absence_in_answered_pop_section',absence_rule_evidence={'sha256':'a'*64});r=pop.evaluate(a,CATALOG,[('1','2026-09')],ps,c,q);fs=pop.findings(ps,r);self.assertTrue(fs);self.assertTrue(all(f['severity']=='info' for f in fs));self.assertEqual(r['monthly'][0]['value'],0)
 def test_dependency_finding_preserves_old_ps_and_does_not_invent_score(self):
  a,ps,c,q=inputs({'g/marcas_material_bebidas':'pepsi','g/categorias_material':'bebidas_sin_alcohol lacteos','g/marcas_material_lacteos':''});r=pop.evaluate(a,CATALOG,[('1','2026-09')],ps,c,q);before=copy.deepcopy(ps);fs=pop.findings(ps,r);self.assertTrue(any(f['rule']=='ps_pop_company_scope_not_supported' for f in fs));self.assertEqual(ps,before)

if __name__=='__main__':unittest.main()
