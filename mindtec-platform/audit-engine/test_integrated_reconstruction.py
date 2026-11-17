import copy,tempfile,unittest
from pathlib import Path
import integrated_reconstruction as combined,integrated_transport as transport
import numeric_distribution,shelf_share
from perfect_store import evaluate
from test_perfect_store import adapter,CATALOG,CONFIG

def fixture(overrides=None):
 a=adapter(overrides);ps=evaluate(a,CATALOG,{'exclusions':[]},CONFIG);nd=numeric_distribution.evaluate(ps,CATALOG,[('1','2026-09')]);sh=shelf_share.evaluate(a,CATALOG,[('1','2026-09')],ps['eligibility_checks'],ps['answer_evidence'],ps['cells']);sources={name:{'run_id':name+'-run','snapshot_sha256':name+'-snapshot','rule_version':'synthetic'} for name in ['perfect_store','distribution','shelf']}
 for r in [nd,sh]:r.update(source_ps_run_id=sources['perfect_store']['run_id'],source_ps_snapshot_sha256=sources['perfect_store']['snapshot_sha256'])
 return ps,nd,sh,sources

class ProjectionTests(unittest.TestCase):
 def test_projects_three_values_without_recalculating_them(self):
  ps,nd,sh,src=fixture();r=combined.project(ps,nd,sh,src);self.assertEqual(len(r['series']),2);s=next(s for s in r['series'] if s['kind']=='month');self.assertEqual(s['ps']['value'],75);self.assertEqual(s['nd']['value'],100);self.assertIsNone(s['sh']['value']);self.assertEqual(r['ps_details'][r['stores'][0]['ps']]['source_index'],0)
 def test_mixed_source_execution_and_snapshot_rejected(self):
  for field in ['source_ps_run_id','source_ps_snapshot_sha256']:
   ps,nd,sh,src=fixture();sh[field]='different'
   with self.assertRaises(ValueError):combined.project(ps,nd,sh,src)
 def test_mixed_book_and_missing_store_rejected(self):
  ps,nd,sh,src=fixture();nd['source_sha256']='different'
  with self.assertRaises(ValueError):combined.project(ps,nd,sh,src)
  ps,nd,sh,src=fixture();sh['stores']=[]
  with self.assertRaises(ValueError):combined.project(ps,nd,sh,src)
 def test_conflicting_fingerprint_cannot_be_merged(self):
  ps,nd,sh,src=fixture();key=next(iter(sh['cells']));sh['cells'][key]['value']='changed'
  with self.assertRaises(ValueError):combined.project(ps,nd,sh,src)
 def test_no_eligible_base_does_not_invent_a_ps_zero(self):
  ps,nd,sh,src=fixture({'g/vende_bsa_gaseosas':'no','g/marcas_bsa_gaseosas':''});r=combined.project(ps,nd,sh,src);self.assertIsNone(r['stores'][0]['ps']);self.assertEqual(r['series'][0]['ps']['state'],'no_eligible_base');self.assertIsNone(r['series'][0]['ps']['value'])
 def test_transport_restores_every_identifier_and_source_cell(self):
  ps,nd,sh,src=fixture();r=combined.project(ps,nd,sh,src);before=copy.deepcopy(r);p,t=transport.pack(r);self.assertEqual(r,before);self.assertTrue(t['lossless']);self.assertIsInstance(p['cells'],list);self.assertEqual(transport.restore(p,t),r)
 def test_transport_restores_finding_and_unattributed_cell_references(self):
  ps,nd,sh,src=fixture();r=combined.project(ps,nd,sh,src);cid=next(iter(r['cells']));aid=next(iter(r['answer_evidence']));r['inventories'][0]['unattributed']=[{'cell_id':cid,'candidate_routes':['one','two']}];r['findings']=[{'origin':'shelf','finding':{'evidence':{'cell_id':cid,'cell_ids':[cid],'answer_ids':[aid]}}}];p,t=transport.pack(r);self.assertEqual(transport.restore(p,t),r)
 def test_borrowed_maps_and_inputs_not_mutated(self):
  ps,nd,sh,src=fixture();before=copy.deepcopy([ps,nd,sh,src]);combined.project(ps,nd,sh,src);self.assertEqual([ps,nd,sh,src],before)
 def test_missing_source_custody_is_not_created(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp)
   with self.assertRaises(ValueError):combined.captured(root/'absent','operational_perfect_store')
   self.assertFalse((root/'absent').exists())

class ColdProjectionTests(unittest.TestCase):
 def inputs(self):
  import cold_share
  ps,nd,sh,sources=fixture();a=adapter();cold=cold_share.evaluate(a,CATALOG,[('1','2026-09')],ps['eligibility_checks'],ps['answer_evidence'],ps['cells']);cold.update(source_ps_run_id=sources['perfect_store']['run_id'],source_ps_snapshot_sha256=sources['perfect_store']['snapshot_sha256']);return combined.project(ps,nd,sh,sources),cold,{'run_id':'cold-run','snapshot_sha256':'cold-snapshot','rule_version':'synthetic'}
 def test_fourth_metric_preserves_original_three_and_roundtrips(self):
  base,cold,meta=self.inputs();before=copy.deepcopy(base);r=combined.attach_cold(base,cold,meta);self.assertEqual(base,before)
  for old,new in zip(base['series'],r['series']):
   for key in ['ps','nd','sh']:self.assertEqual(old[key],new[key])
   self.assertEqual(new['cf']['state'],'zero_observed_faces');self.assertIsNone(new['cf']['value'])
  p,t=transport.pack(r);self.assertEqual(transport.restore(p,t),r);self.assertEqual(r['sources']['cold'],meta)
 def test_incompatible_cold_sources_rejected(self):
  for field in ['source_ps_run_id','source_ps_snapshot_sha256','source_sha256']:
   base,cold,meta=self.inputs();cold[field]='different'
   with self.assertRaises(ValueError):combined.attach_cold(base,cold,meta)
 def test_cold_visits_and_inventory_scope_must_match(self):
  for key in ['stores','category_inventories']:
   base,cold,meta=self.inputs();cold[key]=[]
   with self.assertRaises(ValueError):combined.attach_cold(base,cold,meta)
 def test_cold_aggregate_does_not_silently_omit_a_store(self):
  base,cold,meta=self.inputs();cold['monthly'][0]['store_rows']=[]
  with self.assertRaises(ValueError):combined.attach_cold(base,cold,meta)
 def test_original_gate_and_cold_denominator_not_overwritten(self):
  for key,value in [('source_eligible',False),('category_faces',3)]:
   base,cold,meta=self.inputs();cold['stores'][0][key]=value
   with self.assertRaises(ValueError):combined.attach_cold(base,cold,meta)
 def test_corrupt_cold_evidence_cannot_be_merged(self):
  base,cold,meta=self.inputs();next(iter(cold['cells'].values()))['value']='altered'
  with self.assertRaises(ValueError):combined.attach_cold(base,cold,meta)

if __name__=='__main__':unittest.main()
