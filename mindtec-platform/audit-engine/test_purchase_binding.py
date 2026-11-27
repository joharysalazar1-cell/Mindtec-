import copy,unittest
import purchase_binding as binding,weighted_inputs as w
from flat_answers import FlatAnswers
from test_flat_answers import fixture

HEADER='Cuando compras, ¿a cuánto equivale cada compra de productos de ${empresa_label}?[{index}]'

def inputs(value='300_1000'):
 book,history=fixture(['Company[1]',HEADER.replace('{index}','1')],['embol',value],[('rep_empresa_compra[1]/empresa_actual','Company','embol')]);flat=FlatAnswers(book,history)
 config={'schema':'mindtec-purchase-header-binding/1','version':'synthetic','source_sha256':flat.source_sha256,'forms':{'form':{'repeat':'rep_empresa_compra','field':'monto_compra_empresa','header_template':HEADER}},'observations':[{'form':'form','sha256':'b'*64}]}
 return flat,config

class Tests(unittest.TestCase):
 def test_exact_alias_recovers_amount_and_preserves_original_absent_route(self):
  flat,q=inputs();before=copy.deepcopy(q);r=w.purchase_declarations(flat,flat.records[0],q);row=r['rows'][0];self.assertEqual(row['company'],'embol');self.assertEqual(row['amount_raw'],'300_1000');self.assertEqual(row['amount_state'],'observed');self.assertEqual(row['amount_binding']['original_route_state'],'route_not_mapped');self.assertIsNone(r['monthly_category_purchase']);self.assertEqual(q,before)
  self.assertEqual(flat.query(flat.records[0],'rep_empresa_compra[1]/monto_compra_empresa')['state'],'route_not_mapped')
  self.assertTrue(any(a['state']=='route_not_mapped' and a['route']=='rep_empresa_compra[1]/monto_compra_empresa' for a in r['answers']))
 def test_empty_cell_is_not_zero(self):
  f,q=inputs('');r=w.purchase_declarations(f,f.records[0],q);self.assertIsNone(r['rows'][0]['amount_raw']);self.assertEqual(r['rows'][0]['amount_state'],'empty_observation')
 def test_wrong_cut_form_field_or_missing_observation_rejected(self):
  for what in ['source','forms','field','evidence','header']:
   f,q=inputs()
   if what=='source':q['source_sha256']='wrong'
   elif what=='forms':q['forms']={'other':q['forms']['form']}
   elif what=='field':q['forms']['form']['field']='other'
   elif what=='evidence':q['observations']=[]
   else:q['forms']['form']['header_template']='Guessed {index}'
   with self.assertRaises(ValueError):w.purchase_declarations(f,f.records[0],q)
 def test_existing_route_conflict_cannot_be_overridden(self):
  f,q=inputs();a={'route':'rep_empresa_compra[1]/monto_compra_empresa','state':'observed','value':'menos_300','cells':[]}
  with self.assertRaises(ValueError):binding.resolve(f,f.records[0],'rep_empresa_compra[1]',a,q)
  a['value']='300_1000';self.assertIsNone(binding.resolve(f,f.records[0],'rep_empresa_compra[1]',a,q)[1])
 def test_absent_or_duplicate_exact_header_rejected(self):
  for duplicate in [False,True]:
   f,q=inputs()
   if duplicate:f.headers.append(f.headers[-1])
   else:f.headers[-1]='different'
   with self.assertRaises(ValueError):w.purchase_declarations(f,f.records[0],q)

if __name__=='__main__':unittest.main()
