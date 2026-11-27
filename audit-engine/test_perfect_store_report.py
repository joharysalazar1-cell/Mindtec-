import copy,unittest
from perfect_store_report import pack_references,restore_references
from perfect_store import evaluate
from perfect_store_check import verify_model
from test_perfect_store import adapter,CATALOG,CONFIG

class ProjectionTests(unittest.TestCase):
 def test_all_fingerprint_references_are_reversibly_indexed(self):
  original=evaluate(adapter(),CATALOG,{'exclusions':[]},CONFIG);packed=copy.deepcopy(original);transport=pack_references(packed)
  self.assertIsInstance(packed['cells'],list);self.assertIsInstance(packed['details'][0]['eligibility_evidence'],int)
  restored=restore_references(packed,transport);self.assertEqual(restored,original);self.assertEqual(verify_model(restored)['store_rows'],1)
 def test_no_evidence_cells_are_omitted_by_projection(self):
  original=evaluate(adapter({'g/tiene_material_marketing':'si'}),CATALOG,{'exclusions':[]},CONFIG);packed=copy.deepcopy(original);t=pack_references(packed);restored=restore_references(packed,t)
  self.assertEqual(set(restored['cells']),set(original['cells']));self.assertEqual(restored['answer_evidence'],original['answer_evidence'])

if __name__=='__main__':unittest.main()
