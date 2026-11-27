import copy,unittest
import perfect_store_findings as f

def fixture():
 c={'kobo_id':'1','month':'2026-09','parent_code':'lacteos','category':'lac_a','signals':['parent_category_lists_disagree'],'support':['a']}
 return {'source_sha256':'s'*64,'eligibility_checks':[c,dict(c,category='lac_b')],'answer_evidence':{'a':{'cell_ids':['c']}},'cells':{'c':{'value':'lacteos'}}}

class FindingTests(unittest.TestCase):
 def test_group_by_visit_family_and_signal_with_cell_evidence(self):
  result=fixture();before=copy.deepcopy(result);rows=f.evaluate(result)
  self.assertEqual(len(rows),1);self.assertEqual(rows[0]['evidence']['categories'],['lac_a','lac_b']);self.assertEqual(rows[0]['evidence']['cell_ids'],['c']);self.assertEqual(rows[0]['disposition'],'needs_human_review');self.assertEqual(result,before)
 def test_order_independent_fingerprint_and_source_sensitive(self):
  r=fixture();a=f.evaluate(r);r['eligibility_checks'].reverse();self.assertEqual(f.evaluate(r),a)
  r['source_sha256']='b'*64;self.assertNotEqual(f.evaluate(r)[0]['fingerprint'],a[0]['fingerprint'])
 def test_missing_original_evidence_rejected(self):
  r=fixture();r['cells']={}
  with self.assertRaises(ValueError):f.evaluate(r)
 def test_no_signals_means_no_findings(self):
  r=fixture()
  for c in r['eligibility_checks']:c['signals']=[]
  self.assertEqual(f.evaluate(r),[])

if __name__=='__main__':unittest.main()
