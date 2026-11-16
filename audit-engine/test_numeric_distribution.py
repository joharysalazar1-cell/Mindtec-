import copy,itertools,unittest
import numeric_distribution as nd
from perfect_store import evaluate
from test_perfect_store import adapter,CATALOG,CONFIG

class Tests(unittest.TestCase):
 def source(self,values=None):return evaluate(adapter(values),CATALOG,{'exclusions':[]},CONFIG)
 def test_exact_presence_and_explicit_absence(self):
  yes=nd.evaluate(self.source(),CATALOG,[('1','2026-09')]);self.assertEqual(yes['monthly'][0]['value'],100)
  no=nd.evaluate(self.source({'g/marcas_bsa_gaseosas':'another_brand'}),CATALOG,[('1','2026-09')]);self.assertEqual(no['monthly'][0]['value'],0);self.assertEqual(no['monthly'][0]['denominator'],1)
 def test_unanswered_presence_remains_bounded_not_zero(self):
  r=nd.evaluate(self.source({'g/marcas_bsa_gaseosas':''}),CATALOG,[('1','2026-09')]);s=r['monthly'][0];self.assertIsNone(s['value']);self.assertEqual((s['minimum'],s['maximum']),(0,100));self.assertEqual(s['presence_pending_in_eligible'],1)
 def test_all_ineligible_brand_still_appears_without_zero_score(self):
  r=nd.evaluate(self.source({'g/vende_bsa_gaseosas':'no','g/marcas_bsa_gaseosas':''}),CATALOG,[('1','2026-09')]);s=r['monthly'][0];self.assertEqual(s['state'],'no_eligible_base');self.assertIsNone(s['value']);self.assertIsNone(s['minimum']);self.assertEqual(len(r['stores']),1)
 def test_missing_and_extra_scope_cannot_disappear(self):
  for cohort in [[('2','2026-09')],[('1','2026-09'),('2','2026-09')]]:
   with self.assertRaises(ValueError):nd.evaluate(self.source(),CATALOG,cohort)
 def test_pending_category_does_not_contribute_a_confirmed_presence(self):
  r=nd.evaluate(self.source({'g/vende_bsa_gaseosas':'no'}),CATALOG,[('1','2026-09')]);s=r['monthly'][0];self.assertEqual(s['eligibility_pending'],1);self.assertEqual(s['presence_confirmed'],0);self.assertIsNone(s['value'])
 def test_exact_arithmetic_does_not_hide_source_category_signals(self):
  config=copy.deepcopy(CONFIG);config['parent_gate_rules']={'bsa_':{'parent_code':'bebidas_sin_alcohol','broad_suffix':'categorias_vendidas','registry_suffix':'cat_registro_categorias','allowed_registry_codes':['bebidas_sin_alcohol','lacteos']}}
  ps=evaluate(adapter(extra={'g/categorias_vendidas':'bebidas_sin_alcohol lacteos','g/cat_registro_categorias':'lacteos'}),CATALOG,{'exclusions':[]},config);r=nd.evaluate(ps,CATALOG,[('1','2026-09')]);self.assertEqual(r['monthly'][0]['value'],100);self.assertEqual(r['monthly'][0]['store_months_with_category_signals'],1);self.assertIn('parent_category_lists_disagree',r['stores'][0]['category_signals']);self.assertEqual(r['stores'][0]['eligibility_method'],'explicit_subcategory_answer')
 def test_bounds_match_exhaustive_missing_data_assignments(self):
  # Three confirmed eligible stores: one yes, one no, one missing;
  # two stores with unknown eligibility/presence. Enumerate possible worlds.
  base={'brand':'B','brand_code':'b','category':'c','month':'2026-09'}
  rows=[dict(base,id=str(i),eligible=e,presence=p) for i,(e,p) in enumerate([(True,1),(True,0),(True,None),(None,None),(None,None)])];s=nd.aggregate(rows,'2026-09','month');worlds=[]
  for known in [0,1]:
   for unknown in itertools.product([None,0,1],repeat=2):
    vals=[1,0,known]+[v for v in unknown if v is not None];worlds.append(100*sum(vals)/len(vals))
  self.assertAlmostEqual(s['minimum'],min(worlds));self.assertAlmostEqual(s['maximum'],max(worlds))
 def test_year_uses_pooled_counts_not_mean_of_percentages(self):
  base={'brand':'B','brand_code':'b','category':'c','eligible':True}
  rows=[dict(base,id=str(i),month='2026-09',presence=p) for i,p in enumerate([1,0,0])]+[dict(base,id='3',month='2026-10',presence=1)];s=nd.aggregate(rows,'2026','year_observed_months_pooled_ratio');self.assertEqual(s['value'],50);self.assertEqual(s['denominator'],4)
 def test_refs_resolve_and_input_not_mutated(self):
  ps=self.source();before=copy.deepcopy(ps);r=nd.evaluate(ps,CATALOG,[('1','2026-09')]);self.assertEqual(ps,before)
  for row in r['stores']:
   for aid in row['answer_ids']:
    for cid in r['answer_evidence'][aid]['cell_ids']:self.assertIn(cid,r['cells'])

if __name__=='__main__':unittest.main()
