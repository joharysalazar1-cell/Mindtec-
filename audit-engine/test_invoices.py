import copy,unittest
from invoice_core import evaluate,validate_policy
HEADERS=['ID factura','Línea','Mes','Sticker','Total neto','Cantidad','Precio unitario','Descuento línea','Bonificación línea','ICE línea','Fecha de emisión','Distribuidor','Tipo de documento','N.° documento','Subtotal factura','Total factura']
SCOPE={'namespace':'test-invoice-lines','currency':'BOB','period_basis':'collection_month','cohort_id':'synthetic-panel','periods':['2026-09']}
POLICY={'schema':'mindtec-invoice-policy/1','version':'test/1','line_arithmetic':None,'invoice_sum':None}
def row(invoice='test-invoice',line=1,**extra):
 data={'ID factura':invoice,'Línea':line,'Mes':'2026-09','Sticker':'test-store','Total neto':53.33,'Cantidad':12,'Precio unitario':5,'Descuento línea':6.67,'Bonificación línea':0,'ICE línea':2.14,'Fecha de emisión':46286,'Distribuidor':'test-distributor','Tipo de documento':'factura','N.° documento':'test-document','Subtotal factura':53.33,'Total factura':55.47}|extra
 return {'source_row':line+1,'cells':[data[k] for k in HEADERS]}
def cut(*rows):return {'schema':'mindtec-invoice-cut/1','headers':HEADERS,'rows':list(rows),'scope':copy.deepcopy(SCOPE),'provenance':{'date_system':'excel_1900'}}
class Tests(unittest.TestCase):
 def test_no_tax_formula_is_invented(self):
  findings,coverage=evaluate(cut(row()),POLICY)
  self.assertEqual(findings,[]);self.assertFalse(coverage['line_arithmetic_configured'])
  p=copy.deepcopy(POLICY);p['line_arithmetic']={'quantity':'Cantidad','unit_price':'Precio unitario','target':'Total neto','deductions':['Descuento línea'],'additions':[],'tolerance':'0.01','evidence':'Synthetic declared formula excludes tax'}
  self.assertEqual(evaluate(cut(row()),p)[0],[])
  p['line_arithmetic']['additions']=['ICE línea']
  self.assertEqual([f['rule'] for f in evaluate(cut(row()),p)[0]],['invoice_line_arithmetic'])
 def test_duplicate_keys_prevent_cartesian_comparison(self):
  duplicate=row();duplicate['source_row']=3;previous=cut(row(),duplicate);current=cut(row())
  findings,coverage=evaluate(current,POLICY,previous)
  self.assertEqual(coverage['matched_unique_keys'],0);self.assertEqual(coverage['ambiguous_comparison_keys'],1)
  self.assertEqual([f['rule'] for f in findings],['invoice_comparison_ambiguous'])
 def test_scope_change_blocks_additions_and_removals(self):
  a=cut(row());b=cut(row('other',Mes='2026-10'));b['scope']['periods']=['2026-10']
  findings,coverage=evaluate(b,POLICY,a)
  self.assertFalse(coverage['comparison_comparable']);self.assertEqual([f['rule'] for f in findings],['invoice_scope_mismatch'])
 def test_header_repetitions_are_not_summed(self):
  x=cut(row(),row(line=2,**{'Total neto':40}))
  findings,coverage=evaluate(x,POLICY)
  self.assertEqual(findings,[]);self.assertEqual(coverage['invoice_sum_eligible'],0)
  p=copy.deepcopy(POLICY);p['invoice_sum']={'target':'Subtotal factura','line_field':'Total neto','complete_invoices':{'test-invoice':'Synthetic full original'},'tolerance':'0.01','evidence':'Synthetic formula'}
  self.assertEqual([f['rule'] for f in evaluate(x,p)[0]],['invoice_sum_arithmetic'])
 def test_missing_is_not_zero_and_negative_is_not_fraud(self):
  findings,_=evaluate(cut(row(**{'Total neto':None,'Cantidad':-1})),POLICY)
  self.assertEqual({f['rule'] for f in findings},{'invoice_amount_missing','invoice_nonpositive_measure'})
  self.assertTrue(all(f['severity']=='info' for f in findings))
 def test_changes_keep_both_originals_and_separate_format(self):
  a=cut(row(**{'Distribuidor':None}));b=cut(row(**{'Distribuidor':''}))
  findings,_=evaluate(b,POLICY,a,'current-hash','previous-hash')
  self.assertEqual(findings[0]['rule'],'invoice_format_change')
  self.assertEqual(findings[0]['evidence']['previous']['source_sha256'],'previous-hash')
  c=cut(row(**{'Distribuidor':'approved-correction'}))
  self.assertEqual(evaluate(c,POLICY,a)[0][0]['rule'],'invoice_value_change')
 def test_unknown_completeness_or_formula_is_not_assumed(self):
  p=copy.deepcopy(POLICY);p['invoice_sum']={'target':'Subtotal factura','line_field':'Total neto','complete_invoices':{},'tolerance':'0.01','evidence':'test'}
  self.assertEqual(evaluate(cut(row()),p)[1]['invoice_sum_eligible'],0)
  p['invoice_sum']['complete_invoices']={'test-invoice':''}
  with self.assertRaises(ValueError):validate_policy(p)
 def test_document_numbers_are_not_numeric_aliases(self):
  a=cut(row(**{'N.° documento':'001'}));b=cut(row(**{'N.° documento':'1'}))
  self.assertEqual(evaluate(b,POLICY,a)[0][0]['rule'],'invoice_value_change')
 def test_observation_month_is_not_invoice_date(self):
  self.assertEqual(evaluate(cut(row(**{'Fecha de emisión':46200})),POLICY)[0],[])
  self.assertIn('invoice_period_outside_scope',[f['rule'] for f in evaluate(cut(row(Mes='2026-10')),POLICY)[0]])
 def test_removed_records_have_distinct_issue_keys(self):
  a=cut(row('old-one'),row('old-two',line=2,**{'N.° documento':'another-document'}));b=cut(row('new-one'))
  removed=[f for f in evaluate(b,POLICY,a)[0] if f['rule']=='invoice_row_removed']
  self.assertEqual(len(removed),2);self.assertEqual(len({f['issue_key'] for f in removed}),2)
 def test_document_header_alias_keeps_its_exact_source_path(self):
  a=copy.deepcopy(cut(row('one'),row('two',line=2)))
  a['headers'][a['headers'].index('N.° documento')]='N.º documento'
  finding=next(f for f in evaluate(a,POLICY)[0] if f['rule']=='invoice_possible_repeat')
  self.assertIn('N.º documento',finding['evidence']['paths']);self.assertNotIn('N.° documento',finding['evidence']['paths'])
if __name__=='__main__':unittest.main()
