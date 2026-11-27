import copy,unittest
import integrated_availability as attach,integrated_transport as transport
import declared_availability
from test_integrated_reconstruction import fixture
from test_declared_availability import source
from test_perfect_store import CATALOG,CONFIG
import integrated_reconstruction

def inputs():
 a=source();ps,nd,sh,meta=fixture();base=integrated_reconstruction.project(ps,nd,sh,meta)
 q={'schema':'mindtec-company-question-universe/1','version':'synthetic','detailed_workbook_sha256':a.source_sha256,'forms':{'form':{'offered_companies':['embol']}}}
 result=declared_availability.evaluate(a,CATALOG,[('1','2026-09')],CONFIG,q);result.update(source_ps_run_id=meta['perfect_store']['run_id'],source_ps_snapshot_sha256=meta['perfect_store']['snapshot_sha256'])
 return base,result,{'run_id':'availability-run','snapshot_sha256':'availability-snapshot','rule_version':'synthetic'}

class Tests(unittest.TestCase):
 def test_once_per_company_and_period_with_exact_roundtrip(self):
  base,source,meta=inputs();before=copy.deepcopy([base,source]);r=attach.attach(base,source,meta)
  self.assertEqual([base,source],before);self.assertEqual(r['series'],base['series']);self.assertEqual(len(r['availability']['series']),2)
  self.assertEqual(r['availability']['series'][0]['value'],100);self.assertEqual(r['availability']['series'][0]['denominator'],1)
  self.assertEqual(r['availability']['brand_references'][0]['company'],0);self.assertEqual(r['sources']['availability'],meta)
  packed,t=transport.pack(r);self.assertEqual(transport.restore(packed,t),r)
 def test_rejects_incompatible_cuts(self):
  for field in ['source_sha256','source_ps_run_id','source_ps_snapshot_sha256']:
   base,source,meta=inputs();source[field]='other'
   with self.assertRaises(ValueError):attach.attach(base,source,meta)
 def test_rejects_omitted_or_duplicated_visits_and_aggregates(self):
  for name in ['stores','inventories','monthly','annual_observed_months','brand_references']:
   for duplicate in [False,True]:
    base,source,meta=inputs();source[name]=source[name]+source[name] if duplicate else []
    with self.assertRaises(ValueError,msg=name):attach.attach(base,source,meta)
 def test_rejects_aggregate_omission_and_changed_value(self):
  for field,value in [('store_rows',[]),('value',0),('denominator',2),('state','pending_observations'),('months_observed',[])]:
   base,source,meta=inputs();source['monthly'][0][field]=value
   with self.assertRaises(ValueError):attach.attach(base,source,meta)
 def test_rejects_forged_cells_and_missing_answers(self):
  base,source,meta=inputs();next(iter(source['cells'].values()))['value']='changed'
  with self.assertRaises(ValueError):attach.attach(base,source,meta)
  base,source,meta=inputs();source['stores'][0]['answer_ids']=['missing']
  with self.assertRaises(ValueError):attach.attach(base,source,meta)
 def test_company_reference_must_match_historical_owner(self):
  base,source,meta=inputs();source['brand_references'][0]['company']=None
  with self.assertRaises(ValueError):attach.attach(base,source,meta)
 def test_nonbuyer_requires_questionnaire_coverage(self):
  base,source,meta=inputs();source['stores'][0].update(eligible=False,state='not_applicable',questionnaire_covers_company=False)
  with self.assertRaises(ValueError):attach.attach(base,source,meta)
 def test_company_result_not_repeated_for_each_category_reference(self):
  base,source,meta=inputs();base['catalogue'].append(dict(base['catalogue'][0],brand='Another brand',brand_code='another'));source['brand_references'].append(dict(source['brand_references'][0],brand='Another brand',brand_code='another'))
  r=attach.attach(base,source,meta);self.assertEqual(len(r['availability']['brand_references']),2);self.assertEqual(len(r['availability']['series']),2);self.assertEqual(len(r['availability']['stores']),1)

if __name__=='__main__':unittest.main()
