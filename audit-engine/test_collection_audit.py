import copy,unittest
from collection_audit import evaluate,SHEETS

def cut(ids=('1',)):
 tables=[]
 for role,name in SHEETS.items():
  headers=['ID envío','Mes','Sticker','Estado de entrega']
  extras={'visits':{},'shops':{},'brands':{'Subcategoría (código)':'g','Marca (código)':'b','Marca':'Marca','Caras en góndola':3,'Caras en frío':0},'prices':{'Dónde':'gondola','Código Kobo':'sku1','ID SKU':1,'SKU (maestro)':'SKU','Precio Bs':5},'companies':{'Empresa (código)':'e','Empresa':'Empresa','Quiebre':'no'}}[role]
  headers+=list(extras)
  rows=[]
  for i,eid in enumerate(ids,2):
   vals=[eid,'2026-10','s'+eid,'LISTO']+list(extras.values())
   rows.append({'source_row':i,'cells':vals,'coordinates':[chr(65+j)+str(i) for j in range(len(headers))]})
  tables.append({'sheet':name,'headers':headers,'header_coordinates':[chr(65+j)+'1' for j in range(len(headers))],'rows':rows})
 return {'schema':'mindtec-collection-result-cut/1','identity_namespace':'scan_internal_envio_id','provenance':{'original_sha256':'a'*64},'tables':tables}

def setcell(c,role,column,value):
 t=c['tables'][list(SHEETS).index(role)];t['rows'][0]['cells'][t['headers'].index(column)]=value

class CollectionTests(unittest.TestCase):
 def test_monthly_denominators_do_not_mix(self):
  c=cut(('1','2'))
  for t in c['tables']:
   t['rows'][0]['cells'][t['headers'].index('Mes')]='2026-09'
  t=c['tables'][2];t['rows'][0]['cells'][t['headers'].index('Caras en góndola')]=9
  r=evaluate(c,c,{'1':'101','2':'102'})
  self.assertEqual(len(r['brand_metrics']),2)
  self.assertEqual({m['month']:m['measures']['shelf_faces']['denominator'] for m in r['brand_metrics']},{'2026-09':9,'2026-10':3})
  self.assertTrue(all(m['cohort_visits']==1 for m in r['brand_metrics']))
  self.assertEqual(len(r['company_metrics']),2)
 def test_wrong_child_month_cannot_enter_another_month(self):
  c=cut();setcell(c,'brands','Mes','2026-09')
  r=evaluate(c,c,{'1':'101'})
  self.assertEqual(r['brand_metrics'],[])
  self.assertIn('parent_field_disagrees',[f['rule'] for f in r['findings']])
 def test_partial_scope_does_not_infer_deletion(self):
  r=evaluate(cut(),cut(('1','2')),{'1':'101'})
  self.assertEqual(r['coverage']['previous_same_month_not_in_export'],['2'])
  self.assertEqual(r['changes'],[])
 def test_zero_and_missing_are_distinct(self):
  c=cut();r=evaluate(c,c,{'1':'101'})
  self.assertEqual(r['brand_metrics'][0]['measures']['cold_faces']['state'],'zero_category_denominator')
  setcell(c,'brands','Caras en góndola',None);r=evaluate(c,c,{'1':'101'})
  self.assertIsNone(r['brand_metrics'][0]['measures']['shelf_faces']['share_pct'])
  self.assertEqual(r['brand_metrics'][0]['measures']['shelf_faces']['missing_or_ambiguous_rows'],[2])
 def test_exclusions_require_crosswalk(self):
  p={'exclusions':[{'id':'22','reason':'historical'}]}
  self.assertEqual(evaluate(cut(),crosswalk={'1':'22'},policy=p)['coverage']['historical_policy_eligible_visits'],0)
  r=evaluate(cut(),crosswalk={});self.assertEqual(r['coverage']['historical_policy_eligible_visits'],0)
  self.assertEqual(r['coverage']['unmapped_internal_ids'],['1'])
 def test_duplicate_brand_blocks_share(self):
  c=cut();c['tables'][2]['rows'].append(copy.deepcopy(c['tables'][2]['rows'][0]))
  r=evaluate(c,c,{'1':'101'});self.assertIsNone(r['brand_metrics'][0]['measures']['shelf_faces']['share_pct'])
  self.assertIn('ambiguous_row_identity',[f['rule'] for f in r['findings']])
 def test_changed_price_has_exact_coordinates_and_units(self):
  old=cut();new=cut();setcell(new,'prices','Precio Bs',7)
  r=evaluate(new,old,{'1':'101'});change=r['changes'][0]
  self.assertEqual(change['before']['value'],5);self.assertEqual(change['after']['value'],7)
  self.assertEqual(change['after']['coordinate'],'I2')
  self.assertEqual(r['numeric_change_statistics']['prices:Precio Bs']['rmse_change'],2)
 def test_orphan_is_not_silently_joined(self):
  c=cut();setcell(c,'brands','ID envío','999')
  r=evaluate(c,c,{'1':'101'})
  self.assertIn('missing_unique_parent',[f['rule'] for f in r['findings']]);self.assertEqual(r['brand_metrics'],[])
 def test_schema_addition_is_not_a_cell_change(self):
  old=cut();new=cut();t=new['tables'][2];t['headers'].append('Nueva');t['header_coordinates'].append('Z1');t['rows'][0]['cells'].append('x');t['rows'][0]['coordinates'].append('Z2')
  r=evaluate(new,old,{'1':'101'});self.assertEqual(r['changes'],[]);self.assertEqual(len(r['schema_changes']),1)

if __name__=='__main__':unittest.main()
