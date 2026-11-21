import copy,unittest
import integrated_pop,integrated_reconstruction as combined,integrated_transport as transport
import numeric_distribution,shelf_share,declared_pop
from test_declared_pop import inputs
from test_perfect_store import CATALOG

def fixture(extra=None):
 a,ps,c,q=inputs(extra);nd=numeric_distribution.evaluate(ps,CATALOG,[('1','2026-09')]);sh=shelf_share.evaluate(a,CATALOG,[('1','2026-09')],ps['eligibility_checks'],ps['answer_evidence'],ps['cells']);src={name:{'run_id':name,'snapshot_sha256':name+'-snapshot','rule_version':'synthetic'} for name in ['perfect_store','distribution','shelf']}
 for row in [nd,sh]:row.update(source_ps_run_id=src['perfect_store']['run_id'],source_ps_snapshot_sha256=src['perfect_store']['snapshot_sha256'])
 base=combined.project(ps,nd,sh,src);base['configuration']=c;pop=declared_pop.evaluate(a,CATALOG,[('1','2026-09')],ps,c,q);pop.update(source_ps_run_id=src['perfect_store']['run_id'],source_ps_snapshot_sha256=src['perfect_store']['snapshot_sha256'],definition_evidence_sha256='a'*64)
 return base,pop,{'run_id':'pop-run','snapshot_sha256':'pop-snapshot','rule_version':'synthetic'}

class Tests(unittest.TestCase):
 def test_pop_preserves_previous_metrics_and_exact_transport(self):
  base,pop,meta=fixture();before=copy.deepcopy([base,pop]);r=integrated_pop.attach(base,pop,meta);self.assertEqual([base,pop],before)
  for old,new in zip(base['series'],r['series']):
   for key in ['ps','nd','sh']:self.assertEqual(old[key],new[key])
   self.assertEqual(new['pp']['value'],100);self.assertEqual(new['pp']['denominator'],1)
  p,t=transport.pack(r);self.assertEqual(transport.restore(p,t),r);self.assertEqual(r['sources']['pop'],meta)
 def test_wrong_execution_cut_configuration_or_rule_rejected(self):
  for field in ['source_ps_run_id','source_ps_snapshot_sha256','source_sha256','configuration_version','absence_policy']:
   base,pop,meta=fixture();pop[field]='other'
   with self.assertRaises(ValueError):integrated_pop.attach(base,pop,meta)
 def test_missing_or_duplicate_cohort_is_not_silently_omitted(self):
  for name in ['stores','inventories','company_rows','monthly','annual_observed_months']:
   for duplicate in [False,True]:
    base,pop,meta=fixture();pop[name]=pop[name]+pop[name] if duplicate else []
    with self.assertRaises(ValueError,msg=name):integrated_pop.attach(base,pop,meta)
 def test_changed_presence_or_company_link_rejected(self):
  for field,value in [('presence',0),('eligible',False),('company','cbn'),('company_row_index',None),('presence_source_id','other'),('pop',0)]:
   base,pop,meta=fixture();pop['stores'][0][field]=value
   with self.assertRaises(ValueError,msg=field):integrated_pop.attach(base,pop,meta)
 def test_aggregate_references_counts_and_bounds_are_verified(self):
  for field,value in [('store_rows',[]),('denominator',2),('minimum',0),('maximum',0),('value',0),('state','pending_observations')]:
   base,pop,meta=fixture();pop['monthly'][0][field]=value
   with self.assertRaises(ValueError,msg=field):integrated_pop.attach(base,pop,meta)
 def test_forged_evidence_and_missing_support_rejected(self):
  base,pop,meta=fixture();next(iter(pop['cells'].values()))['value']='altered'
  with self.assertRaises(ValueError):integrated_pop.attach(base,pop,meta)
  base,pop,meta=fixture();pop['stores'][0]['answer_ids']=[]
  with self.assertRaises(ValueError):integrated_pop.attach(base,pop,meta)
 def test_real_zero_remains_measured_not_missing(self):
  base,pop,meta=fixture({'g/marcas_material_bebidas':'pepsi'});r=integrated_pop.attach(base,pop,meta);self.assertEqual(r['series'][0]['pp']['value'],0);self.assertEqual(r['stores'][0]['pp']['value'],0)

if __name__=='__main__':unittest.main()
