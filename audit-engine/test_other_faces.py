import unittest
import shelf_share
from test_shelf_share import source
from test_perfect_store import CATALOG

CAT='bsa_gaseosas'

def append(flat,header,value):
 i=len(flat.headers);letters='';n=i+1
 while n:n,k=divmod(n-1,26);letters=chr(65+k)+letters
 flat.headers.append(header);flat.columns[header]=i;flat.table['header_coordinates'].append(letters+'1');flat.records[0]['row']['cells'].append(value);flat.records[0]['row']['coordinates'].append(letters+'2');flat.unmapped[flat.records[0]['form']].append(header)

def nested(second=True,first_ordinal=1,parent_faces='',child_faces=5):
 flat,ps=source({'rep_'+CAT+'[2]/marca_act_'+CAT:'otras_marcas','rep_'+CAT+'[2]/caras_'+CAT:parent_faces,'rep_'+CAT+'[2]/n_otras_marcas_'+CAT:2}, {'g/marcas_'+CAT:'coca_cola otras_marcas'})
 bases={'ordinal':'num_otra_marca_'+CAT,'name':'Otra marca ${num_otra_marca_'+CAT+'}: ¿cuál es el nombre y SKU completo de la marca? (sabor y volumen)','faces':'¿Cuántas caras de ${otra_marca_sku_'+CAT+'} hay en la exhibición de gaseosas?'}
 for field,value in [('ordinal',first_ordinal),('name','Named product 600ml'),('faces',2)]:append(flat,bases[field]+'[2]',value)
 if second:
  for field,value in [('ordinal',2),('name','Another product 400ml'),('faces',child_faces)]:
   route='rep_'+CAT+'[2]/rep_otras_marcas_'+CAT+'[2]/'+{'ordinal':'num_otra_marca_','name':'otra_marca_sku_','faces':'otra_marca_caras_'}[field]+CAT;append(flat,bases[field]+'[2] ('+route+')',value)
 return flat,ps

def rules(flat,layout='first_child_by_parent_index_then_explicit_paths'):
 return {'schema':'mindtec-other-face-layouts/1','version':'synthetic-layout','detailed_workbook_sha256':flat.source_sha256,'forms':{'form':{'layout':layout}}}

def calculate(flat,ps,config=None):return shelf_share.evaluate(flat,CATALOG,[('1','2026-09')],ps['eligibility_checks'],ps['answer_evidence'],ps['cells'],config)

class Tests(unittest.TestCase):
 def test_nested_children_are_summed_once_with_original_bindings(self):
  flat,ps=nested();r=calculate(flat,ps,rules(flat));s=r['monthly'][0];self.assertEqual((s['numerator'],s['denominator']),(10,17));branch=r['category_inventories'][0]['other_branches'][0];self.assertEqual(branch['faces'],7);self.assertEqual([x['faces'] for x in branch['rows']],[2,5]);self.assertTrue(any('binding_rule' in a for a in r['answer_evidence'].values()))
 def test_no_layout_does_not_infer_nested_binding(self):
  flat,ps=nested();self.assertIsNone(calculate(flat,ps)['monthly'][0]['value'])
 def test_layout_bound_to_exact_workbook(self):
  flat,ps=nested();config=rules(flat);config['detailed_workbook_sha256']='b'*64
  with self.assertRaises(ValueError):calculate(flat,ps,config)
 def test_missing_child_and_wrong_first_ordinal_remain_pending(self):
  for kw in [{'second':False},{'first_ordinal':2}]:
   flat,ps=nested(**kw);self.assertIsNone(calculate(flat,ps,rules(flat))['monthly'][0]['value'])
 def test_parent_and_child_counts_are_never_added_together(self):
  flat,ps=nested(parent_faces=7);r=calculate(flat,ps,rules(flat));self.assertIsNone(r['monthly'][0]['value']);self.assertIn('unexpected_parent_faces_in_nested_branch',r['stores'][0]['signals'])
 def test_noninteger_or_textual_child_faces_remain_pending(self):
  for bad in [-1,.5,True,'5']:
   flat,ps=nested(child_faces=bad);self.assertIsNone(calculate(flat,ps,rules(flat))['monthly'][0]['value'])
 def test_direct_parent_is_an_aggregate_bucket_without_children(self):
  flat,ps=source({'rep_'+CAT+'[2]/marca_act_'+CAT:'otras_marcas','rep_'+CAT+'[2]/caras_'+CAT:5},{'g/marcas_'+CAT:'coca_cola otras_marcas'});r=calculate(flat,ps,rules(flat,'direct_parent_faces'));self.assertEqual(r['monthly'][0]['denominator'],15)
 def test_direct_layout_rejects_a_present_child_counter(self):
  flat,ps=nested();r=calculate(flat,ps,rules(flat,'direct_parent_faces'));self.assertIsNone(r['monthly'][0]['value']);self.assertIn('other_layout_conflict',r['stores'][0]['signals'])
 def test_direct_layout_does_not_ignore_a_mapped_nested_face(self):
  flat,ps=source({'rep_'+CAT+'[2]/marca_act_'+CAT:'otras_marcas','rep_'+CAT+'[2]/caras_'+CAT:5,'rep_'+CAT+'[2]/rep_otras_marcas_'+CAT+'[1]/otra_marca_caras_'+CAT:5},{'g/marcas_'+CAT:'coca_cola otras_marcas'});r=calculate(flat,ps,rules(flat,'direct_parent_faces'));self.assertIsNone(r['monthly'][0]['value']);self.assertIn('other_layout_conflict',r['stores'][0]['signals'])
 def test_explicit_wrong_parent_path_is_not_attached_to_current_parent(self):
  flat,ps=nested(second=False);append(flat,'num_otra_marca_'+CAT+'[2] (rep_'+CAT+'[3]/rep_otras_marcas_'+CAT+'[2]/num_otra_marca_'+CAT+')',2);r=calculate(flat,ps,rules(flat));self.assertIsNone(r['monthly'][0]['value']);self.assertIn('unmapped_other_brand_observation',r['stores'][0]['signals'])

if __name__=='__main__':unittest.main()
