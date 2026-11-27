import copy,unittest
import integrated_conversion as join,integrated_reconstruction as combined,integrated_transport as transport
import cold_conversion,perfect_store,shelf_share
from test_cold_conversion import fixture
from test_perfect_store import CONFIG

def inputs():
 a,c,n,f,q=fixture();ps=perfect_store.evaluate(a,c,{'exclusions':[]},CONFIG);sh=shelf_share.evaluate(a,c,[('1','2026-09')],ps['eligibility_checks'],ps['answer_evidence'],ps['cells'])
 sh.update(source_ps_run_id='ps-run',source_ps_snapshot_sha256='ps-snapshot')
 sources={'perfect_store':{'run_id':'ps-run','snapshot_sha256':'ps-snapshot'},'distribution':{'run_id':'nd','snapshot_sha256':'nd-snapshot'},'shelf':{'run_id':'sh','snapshot_sha256':'sh-snapshot'}}
 base=combined.project(ps,n,sh,sources);meta={'run_id':'cold','snapshot_sha256':'cold-snapshot'};base=combined.attach_cold(base,f,meta)
 r=cold_conversion.evaluate(a,c,[('1','2026-09')],n,f,q);r.update(source_distribution=sources['distribution'],source_cold=meta)
 return base,r,{'run_id':'conversion','snapshot_sha256':'conversion-snapshot'}

class Tests(unittest.TestCase):
 def test_preserves_previous_metrics_and_lossless_transport(self):
  b,s,m=inputs();before=copy.deepcopy([b,s]);r=join.attach(b,s,m);self.assertEqual([b,s],before)
  for key in ['series','stores','visits','catalogue','gates','inventories','ps_details','cold_inventories']:self.assertEqual(r[key],b[key])
  self.assertEqual(r['conversion']['monthly'][0]['value'],100)
  p,t=transport.pack(r);self.assertEqual(transport.restore(p,t),r)
 def test_incompatible_provenance_rejected(self):
  for field in ['unit','source_sha256','source_ps_run_id','source_ps_snapshot_sha256']:
   b,s,m=inputs();s[field]='wrong'
   with self.assertRaises(ValueError):join.attach(b,s,m)
 def test_missing_duplicate_cohort_and_aggregate_rejected(self):
  for field in ['stores','equipment','brand_families','monthly','annual_observed_months']:
   for duplicate in [False,True]:
    b,s,m=inputs();s[field]=s[field]*2 if duplicate else []
    with self.assertRaises(ValueError,msg=field):join.attach(b,s,m)
 def test_changed_presence_denominator_or_count_rejected(self):
  for field,value in [('presence',0),('eligible',False),('operating_equipment',0),('presence_source_indices',[]),('answer_ids',[])]:
   b,s,m=inputs();s['stores'][0][field]=value
   with self.assertRaises(ValueError,msg=field):join.attach(b,s,m)
  for field,value in [('value',0),('denominator',2),('store_rows',[])]:
   b,s,m=inputs();s['monthly'][0][field]=value
   with self.assertRaises(ValueError,msg=field):join.attach(b,s,m)
 def test_altered_cell_rejected(self):
  b,s,m=inputs();next(iter(s['cells'].values()))['value']='changed'
  with self.assertRaises(ValueError):join.attach(b,s,m)

if __name__=='__main__':unittest.main()
