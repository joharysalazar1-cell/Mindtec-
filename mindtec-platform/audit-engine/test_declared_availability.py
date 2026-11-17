import copy,unittest
import declared_availability as metric
from test_perfect_store import adapter,CATALOG,CONFIG

def source(extra=None,overrides=None):
 return adapter(overrides,{'g/n_empresas_compra':1,**(extra or {})})

class Tests(unittest.TestCase):
 def calc(self,a,config=None):
  config=config or CONFIG;choices=sorted((set(config['company_aliases'].values())|set(config['company_by_brand'].values()))-metric.UNVERIFIED);q={'schema':'mindtec-company-question-universe/1','version':'synthetic','detailed_workbook_sha256':a.source_sha256,'forms':{'form':{'offered_companies':choices}}};return metric.evaluate(a,CATALOG,[('1','2026-09')],config,q)
 def test_company_metric_and_brand_reference_are_distinct(self):
  r=self.calc(source());self.assertEqual(r['monthly'][0]['value'],100);self.assertEqual(r['monthly'][0]['denominator'],1);self.assertEqual(r['brand_references'][0]['company'],'embol');self.assertIn('Not a separate brand',r['brand_references'][0]['interpretation'])
 def test_stockout_is_measured_failure_not_missing(self):
  r=self.calc(source({'rep_stock_empresa[1]/hay_quiebre_empresa':'si','rep_stock_empresa[1]/marca_quiebre':'One product'}));self.assertEqual(r['monthly'][0]['value'],0);self.assertEqual(r['monthly'][0]['stockout_numerator'],1)
 def test_missing_binary_is_not_no_stockout(self):
  r=self.calc(source({'rep_stock_empresa[1]/hay_quiebre_empresa':''}));self.assertIsNone(r['monthly'][0]['value']);self.assertIn('stockout_declaration_unresolved',r['stores'][0]['signals'])
 def test_no_with_stockout_details_is_a_conflict(self):
  r=self.calc(source({'rep_stock_empresa[1]/marca_quiebre':'Product'}));self.assertIsNone(r['monthly'][0]['value']);self.assertIn('negative_stockout_with_positive_details',r['stores'][0]['signals'])
 def test_unobserved_other_company_does_not_become_zero_percent(self):
  cfg=copy.deepcopy(CONFIG);cfg['company_aliases']['other']='other';r=self.calc(source(),cfg);s=next(s for s in r['monthly'] if s['company']=='other');self.assertEqual(s['state'],'no_declared_buyers');self.assertIsNone(s['value'])
 def test_incomplete_selector_or_stock_rows_keeps_all_scopes_pending(self):
  for extra in [{'g/n_empresas_compra':2},{'g/n_empresas_compra':''},{'rep_stock_empresa[1]/empresa_actual_stock':''}]:
   r=self.calc(source(extra));self.assertIsNone(r['monthly'][0]['value']);self.assertIsNone(r['stores'][0]['eligible'])
 def test_duplicate_aliases_are_not_silently_deduplicated(self):
  r=self.calc(source({'g/n_empresas_compra':2},{'g/empresas_compra':'embol EMBOL'}));self.assertIn('duplicate_purchase_company',r['inventories'][0]['scope_signals']);self.assertIsNone(r['monthly'][0]['value'])
 def test_unknown_company_is_not_invented_homologation(self):
  r=self.calc(source(overrides={'g/empresas_compra':'unknown'}));self.assertIn('purchase_company_not_homologated',r['inventories'][0]['scope_signals']);self.assertIsNone(r['monthly'][0]['value'])
 def test_empty_scope_requires_explicit_zero_and_no_rows(self):
  a=source({'g/n_empresas_compra':0,'rep_stock_empresa[1]/empresa_actual_stock':'','rep_stock_empresa[1]/hay_quiebre_empresa':''},{'g/empresas_compra':''});r=self.calc(a);self.assertEqual(r['monthly'][0]['state'],'no_declared_buyers')
 def test_repetition_identity_and_expected_count_are_enforced(self):
  a=source({'g/n_empresas_compra':2,'rep_stock_empresa[2]/empresa_actual_stock':'embol','rep_stock_empresa[2]/hay_quiebre_empresa':'no'},{'g/empresas_compra':'embol other'});r=self.calc(a);self.assertIn('duplicate_stock_company',r['inventories'][0]['scope_signals']);self.assertIsNone(r['monthly'][0]['value'])
 def test_owner_missing_or_sentinel_stays_unmapped(self):
  for owners in [{},{'cocacola':'sincorrespondenciaverificada'}]:
   cfg=copy.deepcopy(CONFIG);cfg['company_by_brand']=owners;r=self.calc(source(),cfg);self.assertIsNone(r['brand_references'][0]['company'])
 def test_annual_pools_company_buyers_and_keeps_unknown_visits(self):
  base={'id':'a','company':'c','eligible':True,'state':'complete'};rows=[dict(base,month='2026-09',no_declared_stockout=1),dict(base,month='2026-10',no_declared_stockout=0),dict(base,month='2026-10',no_declared_stockout=0)];self.assertEqual(metric.aggregate(rows,'2026','year')['value'],100/3);rows[0]['state']='pending';self.assertIsNone(metric.aggregate(rows,'2026','year')['value'])
 def test_original_inputs_not_mutated_and_cell_ids_resolve(self):
  a=source();cfg=copy.deepcopy(CONFIG);r=self.calc(a,cfg);self.assertEqual(cfg,CONFIG)
  for row in r['stores']:
   for aid in row['answer_ids']:
    for cid in r['answer_evidence'][aid]['cell_ids']:self.assertIn(cid,r['cells'])
 def test_bad_cohort_rejected(self):
  with self.assertRaises(ValueError):metric.evaluate(source(),CATALOG,[('missing','2026-09')],CONFIG)

class QuestionScopeTests(unittest.TestCase):
 def test_unoffered_company_is_not_treated_as_nonbuyer(self):
  a=source();cfg=copy.deepcopy(CONFIG);cfg['company_aliases']['other']='other';q={'schema':'mindtec-company-question-universe/1','version':'test','detailed_workbook_sha256':a.source_sha256,'forms':{'form':{'offered_companies':['embol']}}};r=metric.evaluate(a,CATALOG,[('1','2026-09')],cfg,q);s=next(s for s in r['monthly'] if s['company']=='other');self.assertEqual(s['state'],'not_covered_by_questionnaire');self.assertIsNone(s['value']);self.assertIsNone(s['denominator'])
 def test_without_admitted_choices_unlisted_companies_remain_unknown(self):
  a=source();cfg=copy.deepcopy(CONFIG);cfg['company_aliases']['other']='other';r=metric.evaluate(a,CATALOG,[('1','2026-09')],cfg);self.assertEqual(next(s for s in r['monthly'] if s['company']=='other')['state'],'pending_observations')
 def test_annual_does_not_omit_an_unoffered_month(self):
  rows=[{'id':'a','company':'c','month':'2026-09','eligible':True,'state':'complete','no_declared_stockout':1},{'id':'b','company':'c','month':'2026-10','eligible':None,'state':'not_covered_by_questionnaire','no_declared_stockout':None}];s=metric.aggregate(rows,'2026','year');self.assertEqual(s['state'],'pending_observations');self.assertIsNone(s['value']);self.assertEqual(s['not_covered_store_months'],1)
 def test_bad_question_source_rejected(self):
  a=source();q={'schema':'mindtec-company-question-universe/1','version':'test','detailed_workbook_sha256':'wrong','forms':{'form':{'offered_companies':['embol']}}}
  with self.assertRaises(ValueError):metric.evaluate(a,CATALOG,[('1','2026-09')],CONFIG,q)

class DependencyTests(unittest.TestCase):
 def test_missing_question_choice_flags_na_without_fabricating_corrected_score(self):
  from perfect_store import evaluate
  a=source();cfg=copy.deepcopy(CONFIG);cfg['company_aliases']['other']='other';cfg['company_by_brand']={'cocacola':'other'};ps=evaluate(a,CATALOG,{'exclusions':[]},cfg);next(c for c in ps['details'][0]['components'] if c['component']=='Sin quiebre')['state']='not_applicable';q={'schema':'mindtec-company-question-universe/1','version':'test','detailed_workbook_sha256':a.source_sha256,'forms':{'form':{'offered_companies':['embol']}}};r=metric.evaluate(a,CATALOG,[('1','2026-09')],cfg,q);r.update(source_ps_run_id='synthetic-ps',source_ps_snapshot_sha256='synthetic-snapshot');before=copy.deepcopy(ps);findings=metric.ps_scope_findings(ps,r);self.assertEqual(ps,before);self.assertEqual(len(findings),1);self.assertEqual(findings[0]['evidence']['detail_indices'],[0]);self.assertNotIn('corrected_score',findings[0]['evidence'])
 def test_offered_nonbuyer_does_not_trigger_unoffered_company_finding(self):
  from perfect_store import evaluate
  a=source();ps=evaluate(a,CATALOG,{'exclusions':[]},CONFIG);r=metric.evaluate(a,CATALOG,[('1','2026-09')],CONFIG);r.update(source_ps_run_id='synthetic-ps',source_ps_snapshot_sha256='synthetic-snapshot');self.assertEqual(metric.ps_scope_findings(ps,r),[])

if __name__=='__main__':unittest.main()
