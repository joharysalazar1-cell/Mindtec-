"""Cross-runtime evidence parity for the future hosted invoice evaluator."""
import copy,json,subprocess,unittest
from pathlib import Path
from invoice_core import evaluate
from engine import canonical
from test_invoices import cut,row,POLICY

def web(current,policy=POLICY,previous=None):
 result=subprocess.run(['node',str(Path(__file__).with_name('test-invoice-web.mjs'))],input=canonical({'cut':current,'policy':policy,'reference':previous,'source_hash':'source','reference_hash':'previous'}),text=True,encoding='utf-8',capture_output=True,check=True)
 return json.loads(result.stdout)

class WebTests(unittest.TestCase):
 def parity(self,current,policy=POLICY,previous=None):
  findings,coverage=evaluate(current,policy,previous,'source','previous');actual=web(current,policy,previous)
  self.assertEqual(actual['coverage'],coverage)
  self.assertEqual({f['fingerprint'] for f in actual['findings']},{f['fingerprint'] for f in findings})
  self.assertEqual({f['issue_key'] for f in actual['findings']},{f['issue_key'] for f in findings})
  self.assertTrue(all(f['disposition']=='informational' for f in actual['findings'] if f['severity']=='info'))
  return actual
 def test_structural_and_document_controls(self):
  self.parity(cut(row(**{'Total neto':None,'Cantidad':-1,'Precio unitario':'unreadable','Fecha de emisión':None})))
  self.parity(cut(row('a'),row('b',line=2)))
  self.parity(cut(row(),row(line=2,Distribuidor='different')))
  self.parity(cut(row(**{'Fecha de emisión':60})))
  a=row();b=row();b['source_row']=3;self.parity(cut(a,b))
 def test_crosscut_changes_and_ambiguity(self):
  old=cut(row(**{'N.° documento':'001','Distribuidor':None}));new=cut(row(**{'N.° documento':'1','Distribuidor':''}));self.parity(new,previous=old)
  a=row();b=row();b['source_row']=3;self.parity(cut(a),previous=cut(a,b))
  self.parity(cut(row('new')),previous=cut(row('old')))
  scoped=cut(row());scoped['scope']['periods']=['2026-10'];self.parity(scoped,previous=cut(row()))
 def test_unicode_across_pipe_chunks_preserves_evidence(self):
  old=cut(*[row('invoice-'+str(i),line=i+1,**{'Distribuidor':'áéíóú ñ '*400}) for i in range(30)])
  new=copy.deepcopy(old);new['rows'][-1]['cells'][new['headers'].index('Distribuidor')]='Corrección documentada'
  self.parity(new,previous=old)
 def test_declared_decimal_formula_and_completeness(self):
  policy=copy.deepcopy(POLICY);policy['line_arithmetic']={'quantity':'Cantidad','unit_price':'Precio unitario','target':'Total neto','deductions':['Descuento línea'],'additions':['ICE línea'],'tolerance':'0.01','evidence':'Synthetic explicit formula'}
  self.parity(cut(row()),policy)
  policy['invoice_sum']={'target':'Subtotal factura','line_field':'Total neto','complete_invoices':{'test-invoice':'Synthetic complete original'},'tolerance':'0.01','evidence':'Synthetic explicit terms'}
  self.parity(cut(row(),row(line=2,**{'Total neto':40})),policy)
  # Exact tolerance boundary must not become a floating point false positive.
  r=row(**{'Cantidad':'0.1','Precio unitario':'0.2','Total neto':'0.03','Descuento línea':'0','ICE línea':'0'})
  p=copy.deepcopy(policy);p['invoice_sum']=None;self.parity(cut(r),p)
 def test_rejects_unsafe_or_incomplete_contracts(self):
  for mutate in [lambda c:c['rows'][0]['cells'].append('extra'),lambda c:c['rows'].append(copy.deepcopy(c['rows'][0])),lambda c:c['rows'][0]['cells'].__setitem__(0,{'nested':'not a cell'}),lambda c:c['rows'][0]['cells'].__setitem__(0,9007199254740993)]:
   c=cut(row());mutate(c)
   with self.assertRaises(subprocess.CalledProcessError):web(c)

if __name__=='__main__':unittest.main()
