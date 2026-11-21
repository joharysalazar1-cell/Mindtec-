import copy,unittest
from perfect_store import evaluate
from perfect_store_check import verify_model,verify_cells
from test_perfect_store import adapter,CATALOG,CONFIG

class CheckTests(unittest.TestCase):
 def setUp(self):
  self.flat=adapter();self.result=evaluate(self.flat,CATALOG,{'exclusions':[]},CONFIG);self.workbook={'provenance':self.flat.provenance,'tables':[self.flat.table]}
 def test_real_cell_values_and_arithmetic_checked_separately(self):
  self.assertEqual(verify_model(self.result)['store_rows'],1);self.assertGreater(verify_cells(self.result,self.workbook)['verified_original_cells'],0)
 def test_rehashed_cell_tampering_still_fails_original_comparison(self):
  r=copy.deepcopy(self.result);c=next(iter(r['cells'].values()));c['value']='changed'
  with self.assertRaisesRegex(ValueError,'original workbook'):verify_cells(r,self.workbook)
 def test_wrong_store_score_and_wrong_aggregate_rejected(self):
  r=copy.deepcopy(self.result);r['details'][0]['score']=99
  with self.assertRaisesRegex(ValueError,'arithmetic'):verify_model(r)
  r=copy.deepcopy(self.result);r['monthly'][0]['score']=99
  with self.assertRaisesRegex(ValueError,'arithmetic'):verify_model(r)

if __name__=='__main__':unittest.main()
