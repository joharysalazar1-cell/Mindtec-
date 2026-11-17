import unittest
import engine
from flat_answers import FlatAnswers
from perfect_store import evaluate,COMPONENTS
from test_flat_answers import fixture

CATALOG=[{'category':'bsa_gaseosas','brand_code':'coca_cola','brand':'Coca-Cola'}]
KEY=engine.canonical(['bsa_gaseosas','coca_cola','Coca-Cola'])
CONFIG={'schema':'mindtec-operational-perfect-store-config/1','version':'synthetic','weights':{c:1 for c in COMPONENTS},'cooler_rule':'coca_cola_any_operating_vertical_others_no_coca_exclusive','company_by_brand':{'cocacola':'embol'},'company_aliases':{'embol':'embol'},'reference_skus_by_catalog':{KEY:['Required SKU']}}

def adapter(overrides=None,extra=None):
 values={'g/vende_bsa_gaseosas':'si','g/marcas_bsa_gaseosas':'coca_cola','g/hay_enfriadores':'no','g/tiene_material_marketing':'no','g/empresas_compra':'embol','g/n_skus_precio':1,'rep_precio[1]/sku_precio_label':'Required SKU','rep_stock_empresa[1]/empresa_actual_stock':'embol','rep_stock_empresa[1]/hay_quiebre_empresa':'no'}
 values.update(overrides or {});values.update(extra or {})
 import re
 answers=[(r,r.split('/')[-1],v) for r,v in values.items()];headers=[q+''.join(re.findall(r'\[\d+\]',r)) for r,q,v in answers]
 w,h=fixture(headers,list(values.values()),answers);return FlatAnswers(w,h)

class PerfectStoreTests(unittest.TestCase):
 def test_result_is_reproducible_across_python_hash_seeds(self):
  import os,subprocess,sys
  from pathlib import Path
  script="""import copy,engine
from test_perfect_store import adapter,CATALOG,CONFIG
from perfect_store import evaluate
c=copy.deepcopy(CONFIG);c['parent_gate_rules']={'bsa_':{'parent_code':'bebidas_sin_alcohol','broad_suffix':'categorias_vendidas','registry_suffix':'cat_registro_categorias','allowed_registry_codes':['bebidas_sin_alcohol','lacteos']}}
a=adapter(extra={'g/categorias_vendidas':'bebidas_sin_alcohol lacteos','g/cat_registro_categorias':'lacteos','g/vende_bsa_agua':'si','g/vende_bsa_jugos':'si'})
print(engine.sha(engine.canonical(evaluate(a,CATALOG,{'exclusions':[]},c))))
"""
  outputs=[subprocess.run([sys.executable,'-c',script],cwd=Path(__file__).parent,env={**os.environ,'PYTHONHASHSEED':seed},capture_output=True,text=True,check=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0)).stdout.strip() for seed in ['11','77','1001']]
  self.assertEqual(len(set(outputs)),1)
 def test_parent_exclusion_requires_agreement_and_retains_support(self):
  import copy
  config=copy.deepcopy(CONFIG);config['parent_gate_rules']={'bsa_':{'parent_code':'bebidas_sin_alcohol','broad_suffix':'categorias_vendidas','registry_suffix':'cat_registro_categorias','allowed_registry_codes':['bebidas_sin_alcohol','lacteos']}}
  values={'g/vende_bsa_gaseosas':'','g/marcas_bsa_gaseosas':'','g/categorias_vendidas':'lacteos','g/cat_registro_categorias':'lacteos'}
  r=evaluate(adapter(values),CATALOG,{'exclusions':[]},config)
  self.assertEqual(r['details'],[]);row=r['explicitly_ineligible'][0];self.assertEqual(row['eligibility_method'],'agreed_explicit_parent_exclusion');self.assertEqual(len(row['eligibility_support']),4)
  values['g/categorias_vendidas']='bebidas_sin_alcohol lacteos';r=evaluate(adapter(values),CATALOG,{'exclusions':[]},config)
  self.assertIsNone(r['details'][0]['eligible']);self.assertIn('parent_category_lists_disagree',r['eligibility_checks'][0]['signals'])
 def run_model(self,a,policy=None):return evaluate(a,CATALOG,policy or {'exclusions':[]},CONFIG)
 def components(self,r):return {c['component']:c for c in r['details'][0]['components']}
 def test_store_denominator_excludes_only_explicit_inapplicability(self):
  r=self.run_model(adapter());d=r['details'][0];self.assertEqual(d['score'],75);self.assertEqual(d['numerator'],3);self.assertEqual(d['measured_denominator'],4);self.assertEqual(self.components(r)['Frío']['state'],'not_applicable')
 def test_empty_presence_does_not_become_zero(self):
  r=self.run_model(adapter({'g/marcas_bsa_gaseosas':''}));self.assertEqual(self.components(r)['Presencia']['state'],'pending');self.assertIsNone(r['monthly'][0]['score'])
 def test_yes_pop_without_brand_list_is_pending_not_zero(self):
  r=self.run_model(adapter({'g/tiene_material_marketing':'si'}));self.assertEqual(self.components(r)['POP']['state'],'pending');self.assertIsNone(r['details'][0]['score']);self.assertLessEqual(r['details'][0]['conditional_minimum'],r['details'][0]['conditional_maximum'])
 def test_incomplete_equipment_rows_are_pending_not_na(self):
  r=self.run_model(adapter({'g/hay_enfriadores':'si'},{'g/cuantos_enfriadores_bsa':2,'rep_enfriador[1]/tipo_enfriador':'nevera_vertical','rep_enfriador[1]/enfriador_encendido':'no'}));self.assertEqual(self.components(r)['Frío']['state'],'pending')
 def test_earlier_form_explicit_total_and_later_form_empty_bsa_count_differ(self):
  extra={'g/cuantos_enfriadores':1,'rep_enfriador[1]/tipo_enfriador':'nevera_vertical','rep_enfriador[1]/enfriador_encendido':'no'}
  r=self.run_model(adapter({'g/hay_enfriadores':'si'},extra));self.assertEqual(self.components(r)['Frío']['state'],'not_applicable')
  extra['g/cuantos_enfriadores_bsa']='';r=self.run_model(adapter({'g/hay_enfriadores':'si'},extra));self.assertEqual(self.components(r)['Frío']['state'],'pending')
 def test_operating_access_and_explicit_complete_zero_cold_is_measured(self):
  extras={'g/cuantos_enfriadores_bsa':1,'rep_enfriador[1]/tipo_enfriador':'nevera_vertical','rep_enfriador[1]/enfriador_encendido':'si','g/n_frio_bsa_gaseosas':1,'rep_frio_bsa_gaseosas[1]/marca_frio_act_bsa_gaseosas':'coca_cola','rep_frio_bsa_gaseosas[1]/caras_frio_bsa_gaseosas':0}
  r=self.run_model(adapter({'g/hay_enfriadores':'si'},extras));self.assertEqual(self.components(r)['Frío']['value'],0);self.assertEqual(r['details'][0]['score'],60)
 def test_explicit_noneligibility_and_exclusions_remain_auditable(self):
  r=self.run_model(adapter({'g/vende_bsa_gaseosas':'no','g/marcas_bsa_gaseosas':''}));self.assertEqual(r['details'],[]);self.assertEqual(len(r['explicitly_ineligible']),1)
  r=self.run_model(adapter(),{'exclusions':[{'id':'1'}]});self.assertEqual(r['details'],[])
 def test_contradictory_noneligibility_not_silently_dropped(self):
  r=self.run_model(adapter({'g/vende_bsa_gaseosas':'no'}));self.assertIsNone(r['details'][0]['eligible']);self.assertIsNone(r['monthly'][0]['score'])
 def test_evidence_links_resolve_to_original_cells(self):
  r=self.run_model(adapter())
  for c in r['details'][0]['components']:
   for aid in c['evidence_ids']:
    self.assertIn(aid,r['answer_evidence'])
    for cid in r['answer_evidence'][aid]['cell_ids']:self.assertEqual(r['cells'][cid]['source_sha256'],'a'*64)
  self.assertEqual(r['annual_observed_months'][0]['months_observed'],['2026-09']);self.assertEqual(r['annual_observed_months'][0]['period_kind'],'year_observed_months_only')

class StockQuestionUniverseTests(unittest.TestCase):
 def setup_case(self,offered=('embol','aje')):
  import base64,copy
  a=adapter(extra={'g/n_empresas_compra':1});cfg=copy.deepcopy(CONFIG);cfg['company_by_brand']={'cocacola':'aje'};cfg['company_aliases']['aje']='aje';raw=b'Synthetic observed company choices';cfg['stock_question_universe']={'schema':'mindtec-company-question-universe/1','version':'test','detailed_workbook_sha256':a.source_sha256,'forms':{'form':{'offered_companies':list(offered)}},'retained_observations':[{'form':'form','original_sha256':engine.sha(raw),'content':base64.b64encode(raw).decode()}]};return a,cfg
 def stock(self,a,cfg):return next(c for c in evaluate(a,CATALOG,{'exclusions':[]},cfg)['details'][0]['components'] if c['component']=='Sin quiebre')
 def test_explicit_offered_nonbuyer_is_na_only_with_complete_enumeration(self):
  a,cfg=self.setup_case();self.assertEqual(self.stock(a,cfg)['state'],'not_applicable');a.records[0]['cache'].clear();route=next(r for r in a.bindings['form'] if r.endswith('/n_empresas_compra'));a.records[0]['row']['cells'][a.bindings['form'][route][0]]=2;self.assertEqual(self.stock(a,cfg)['state'],'pending')
 def test_unoffered_or_unknown_universe_never_proves_nonbuyer(self):
  a,cfg=self.setup_case(('embol',));self.assertEqual(self.stock(a,cfg)['state'],'pending');del cfg['stock_question_universe'];self.assertEqual(self.stock(a,cfg)['state'],'pending')
 def test_question_source_and_observation_hash_are_required(self):
  for field,value in [('detailed_workbook_sha256','wrong'),('retained_observations',[])]:
   a,cfg=self.setup_case();cfg['stock_question_universe'][field]=value
   with self.assertRaises(ValueError):self.stock(a,cfg)
 def test_negative_stockout_with_nonempty_details_is_pending(self):
  a=adapter(extra={'rep_stock_empresa[1]/marca_quiebre':'Product'});self.assertEqual(self.stock(a,CONFIG)['state'],'pending')

if __name__=='__main__':unittest.main()
