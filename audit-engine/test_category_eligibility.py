import unittest
from category_eligibility import decide

def a(v,state='observed'):return {'state':state,'value':v,'cells':[]}
def parent_args():return {'parent_code':'lacteos','broad':a('bebidas_sin_alcohol abarrotes'),'registry':a('bebidas_sin_alcohol'),'allowed_registry_codes':['bebidas_sin_alcohol','lacteos']}

class EligibilityTests(unittest.TestCase):
 def test_agreed_parent_exclusion_resolves_unasked_child(self):
  r=decide(a(None,'empty_observation'),a(None,'empty_observation'),**parent_args());self.assertIs(r['eligible'],False);self.assertEqual(r['method'],'agreed_explicit_parent_exclusion')
 def test_disagreeing_parent_lists_remain_pending(self):
  args=parent_args();args['broad']=a('bebidas_sin_alcohol lacteos');r=decide(a(None,'empty_observation'),a(None,'empty_observation'),**args);self.assertIsNone(r['eligible']);self.assertIn('parent_category_lists_disagree',r['signals'])
 def test_one_missing_parent_or_unknown_registry_code_is_not_negative(self):
  for update in [{'broad':a(None,'empty_observation')},{'registry':a('otros')}]:
   r=decide(a(None,'empty_observation'),a(None,'empty_observation'),**(parent_args()|update));self.assertIsNone(r['eligible'])
 def test_brand_or_sibling_evidence_blocks_inferred_exclusion(self):
  for update in [{'positive_repeat':True},{'positive_sibling':True}]:
   r=decide(a(None,'empty_observation'),a(None,'empty_observation'),**(parent_args()|update));self.assertIsNone(r['eligible'])
 def test_parent_presence_does_not_imply_every_subcategory_is_sold(self):
  r=decide(a('no'),a(None,'empty_observation'),**(parent_args()|{'broad':a('lacteos'),'registry':a('lacteos')}));self.assertIs(r['eligible'],False)
 def test_child_denial_with_any_declared_brand_is_conflict(self):
  r=decide(a('no'),a('another_brand'));self.assertIsNone(r['eligible']);self.assertIn('subcategory_denied_with_brand_evidence',r['signals'])
 def test_explicit_child_yes_is_not_replaced_by_missing_parents(self):
  self.assertIs(decide(a('si'),a('brand'))['eligible'],True)

if __name__=='__main__':unittest.main()
