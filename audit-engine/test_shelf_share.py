import copy,unittest
import shelf_share as share
from perfect_store import evaluate
from test_perfect_store import adapter,CATALOG,CONFIG

def source(extra=None,overrides=None):
 values={'g/n_bsa_gaseosas':2,'rep_bsa_gaseosas[1]/marca_act_bsa_gaseosas':'coca_cola','rep_bsa_gaseosas[1]/marca_lbl_bsa_gaseosas':'Coca-Cola','rep_bsa_gaseosas[1]/caras_bsa_gaseosas':10,'rep_bsa_gaseosas[2]/marca_act_bsa_gaseosas':'pepsi','rep_bsa_gaseosas[2]/marca_lbl_bsa_gaseosas':'Pepsi','rep_bsa_gaseosas[2]/caras_bsa_gaseosas':30};values.update(extra or {});a=adapter({'g/marcas_bsa_gaseosas':'coca_cola pepsi',**(overrides or {})},values);ps=evaluate(a,CATALOG,{'exclusions':[]},CONFIG);return a,ps

class Tests(unittest.TestCase):
 def calc(self,a,ps):return share.evaluate(a,CATALOG,[('1','2026-09')],ps['eligibility_checks'],ps['answer_evidence'],ps['cells'])
 def test_complete_denominator_includes_other_catalogued_brands(self):
  a,ps=source();r=self.calc(a,ps);s=r['monthly'][0];self.assertEqual((s['numerator'],s['denominator'],s['value']),(10,40,25));self.assertEqual(r['stores'][0]['category_faces'],40)
 def test_missing_face_count_blocks_full_share_instead_of_becoming_zero(self):
  a,ps=source({'rep_bsa_gaseosas[2]/caras_bsa_gaseosas':''});r=self.calc(a,ps);self.assertIsNone(r['monthly'][0]['value']);self.assertEqual(r['stores'][0]['known_category_faces_subtotal_not_total'],10);self.assertEqual(r['stores'][0]['known_brand_faces_not_full_share'],10);self.assertIn('face_count_unresolved',r['stores'][0]['signals'])
 def test_expected_repetition_count_prevents_partial_denominator(self):
  a,ps=source({'g/n_bsa_gaseosas':3});r=self.calc(a,ps);self.assertIsNone(r['monthly'][0]['value']);self.assertIn('brand_enumeration_incomplete',r['stores'][0]['signals'])
 def test_other_brands_not_guessed_or_added_twice(self):
  a,ps=source({'rep_bsa_gaseosas[2]/marca_act_bsa_gaseosas':'otras_marcas'},{'g/marcas_bsa_gaseosas':'coca_cola otras_marcas'});r=self.calc(a,ps);self.assertIsNone(r['monthly'][0]['value']);self.assertIn('other_brand_branch_requires_explicit_mapping',r['stores'][0]['signals'])
 def test_duplicate_brand_does_not_select_last_count(self):
  a,ps=source({'rep_bsa_gaseosas[2]/marca_act_bsa_gaseosas':'coca_cola'},{'g/marcas_bsa_gaseosas':'coca_cola'});r=self.calc(a,ps);self.assertIsNone(r['monthly'][0]['value']);self.assertEqual(r['stores'][0]['known_category_faces_subtotal_not_total'],0);self.assertIn('duplicate_brand_row',r['stores'][0]['signals'])
 def test_zero_denominator_and_inapplicability_distinct(self):
  a,ps=source({'rep_bsa_gaseosas[1]/caras_bsa_gaseosas':0,'rep_bsa_gaseosas[2]/caras_bsa_gaseosas':0});s=self.calc(a,ps)['monthly'][0];self.assertEqual(s['state'],'zero_observed_faces');self.assertEqual(s['denominator'],0);self.assertIsNone(s['value'])
  a=adapter({'g/vende_bsa_gaseosas':'no','g/marcas_bsa_gaseosas':''});ps=evaluate(a,CATALOG,{'exclusions':[]},CONFIG);s=self.calc(a,ps)['monthly'][0];self.assertEqual(s['state'],'no_eligible_base');self.assertIsNone(s['value'])
 def test_denied_category_with_observed_brand_rows_stays_pending(self):
  a,ps=source(overrides={'g/vende_bsa_gaseosas':'no','g/marcas_bsa_gaseosas':''});s=self.calc(a,ps)['monthly'][0];self.assertEqual(s['state'],'pending_observations');self.assertIsNone(s['value'])
 def test_zero_numerator_is_a_real_zero_share(self):
  a,ps=source({'rep_bsa_gaseosas[1]/caras_bsa_gaseosas':0});s=self.calc(a,ps)['monthly'][0];self.assertEqual(s['value'],0);self.assertEqual(s['denominator'],30)
 def test_year_pools_faces_not_percentages(self):
  base={'brand':'B','brand_code':'b','category':'c','eligible':True,'state':'complete','category_signals':[]};rows=[dict(base,id='1',month='2026-09',brand_faces=1,category_faces=10),dict(base,id='2',month='2026-10',brand_faces=9,category_faces=90)];s=share.aggregate(rows,'2026','year_observed_months_pooled_faces');self.assertEqual((s['numerator'],s['denominator'],s['value']),(10,100,10))
 def test_counts_reject_negative_fractional_boolean_and_text(self):
  for bad in [-1,0.5,True,'30']:
   a,ps=source({'rep_bsa_gaseosas[2]/caras_bsa_gaseosas':bad});self.assertIsNone(self.calc(a,ps)['monthly'][0]['value'])
 def test_cold_faces_do_not_enter_shelf_denominator(self):
  a,ps=source({'rep_frio_bsa_gaseosas[1]/caras_frio_bsa_gaseosas':999});self.assertEqual(self.calc(a,ps)['monthly'][0]['denominator'],40)
 def add_unmapped(self,a,header,value):
  index=len(a.headers);letters='';n=index+1
  while n:n,k=divmod(n-1,26);letters=chr(65+k)+letters
  a.headers.append(header);a.columns[header]=index;a.table['header_coordinates'].append(letters+'1');a.records[0]['row']['cells'].append(value);a.records[0]['row']['coordinates'].append(letters+'2');a.unmapped[a.records[0]['form']].append(header)
 def test_unmapped_other_face_value_is_preserved_and_blocks_denominator(self):
  a,ps=source();self.add_unmapped(a,'Caras ${otra_marca_sku_bsa_gaseosas}[1]',7);r=self.calc(a,ps);self.assertIsNone(r['monthly'][0]['value']);self.assertIn('unmapped_other_brand_observation',r['stores'][0]['signals']);self.assertTrue(any(c['value']==7 for c in r['cells'].values()))
 def test_similarly_prefixed_category_does_not_contaminate_denominator(self):
  a,ps=source();self.add_unmapped(a,'Caras ${otra_marca_sku_bsa_gaseosas_sin_azucar}[1]',7);r=self.calc(a,ps);self.assertEqual(r['monthly'][0]['value'],25)
 def test_ambiguous_catalogue_code_does_not_duplicate_a_brand_share(self):
  a,ps=source();catalog=CATALOG+[dict(CATALOG[0],brand='Another unresolved label')]
  with self.assertRaises(ValueError):share.evaluate(a,catalog,[('1','2026-09')],ps['eligibility_checks'],ps['answer_evidence'],ps['cells'])
 def test_evidence_resolves_without_mutating_source(self):
  a,ps=source();before=copy.deepcopy(ps);r=self.calc(a,ps);self.assertEqual(ps,before)
  for row in r['stores']:
   for aid in row['answer_ids']:
    for cid in r['answer_evidence'][aid]['cell_ids']:self.assertIn(cid,r['cells'])

if __name__=='__main__':unittest.main()
