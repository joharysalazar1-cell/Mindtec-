import copy,unittest
from flat_answers import FlatAnswers,METADATA

def fixture(columns,values,answers,form='form'):
 headers=METADATA+columns;meta={h:'' for h in METADATA};meta.update({'Envio Kobo':'1','Formulario':form,'Fecha visita':'2026-09-15'})
 def letters(i):
  out=''
  while i:i,n=divmod(i-1,26);out=chr(65+n)+out
  return out
 table={'sheet':'Envíos','headers':headers,'header_coordinates':[letters(i)+'1' for i in range(1,len(headers)+1)],'rows':[{'source_row':2,'cells':[meta[h] for h in METADATA]+values,'coordinates':[letters(i)+'2' for i in range(1,len(headers)+1)]}],'formula_cells_using_cached_values':0}
 workbook={'schema':'mindtec-collection-result-cut/1','provenance':{'original_sha256':'a'*64},'tables':[table]}
 history={'total':1,'envios':[{'envioKobo':'1','formulario':form,'respuestas':[{'ruta':r,'pregunta':q,'valor':v} for r,q,v in answers]}]}
 return workbook,history

class FlatTests(unittest.TestCase):
 def test_new_zero_is_read_from_new_cell_not_old_value(self):
  w,h=fixture(['Count'],[0],[('group/count','Count',9)]);a=FlatAnswers(w,h);v=a.suffix(a.records[0],'count');self.assertEqual(v['state'],'observed');self.assertEqual(v['value'],0);self.assertEqual(v['cells'][0]['coordinate'],'P2')
 def test_empty_stays_unknown_without_historical_fallback(self):
  w,h=fixture(['Count'],[''],[('group/count','Count',9)]);a=FlatAnswers(w,h);v=a.suffix(a.records[0],'count');self.assertEqual(v['state'],'empty_observation');self.assertIsNone(v['value']);self.assertEqual(v['cells'][0]['value'],'')
 def test_ambiguous_question_never_selects_first_route(self):
  w,h=fixture(['Question'],['si'],[('one/value','Question','si'),('two/value','Question','no')]);a=FlatAnswers(w,h);self.assertEqual(a.query(a.records[0],'one/value')['state'],'ambiguous_header_binding')
 def test_exact_form_scope_separates_same_question(self):
  w,h=fixture(['Question'],['si'],[('one/value','Question','no')]);h['envios'].append({'envioKobo':'2','formulario':'other','respuestas':[{'ruta':'two/value','pregunta':'Question','valor':'no'}]});h['total']=2;a=FlatAnswers(w,h);self.assertEqual(a.query(a.records[0],'one/value')['value'],'si');self.assertEqual(a.query(a.records[0],'two/value')['state'],'route_not_mapped')
 def test_repeat_indices_preserve_row_identity(self):
  w,h=fixture(['Count[2]'],[7],[('rep_x[2]/count','Count',9)]);a=FlatAnswers(w,h);g=a.groups(a.records[0],'rep_x');self.assertEqual(g['rep_x[2]']['count']['value'],7)
 def test_empty_fields_of_active_repeat_keep_their_original_cell(self):
  w,h=fixture(['Code[1]','Count[1]'],['brand',''],[('rep_x[1]/code','Code','brand'),('rep_x[1]/count','Count',9)]);a=FlatAnswers(w,h);g=a.groups(a.records[0],'rep_x');self.assertEqual(g['rep_x[1]']['count']['state'],'empty_observation');self.assertEqual(g['rep_x[1]']['count']['cells'][0]['coordinate'],'Q2')
 def test_conflicting_alias_cells_do_not_choose_last(self):
  w,h=fixture(['Question','Question (one/value)'],['si','no'],[('one/value','Question','si')]);a=FlatAnswers(w,h);self.assertEqual(a.query(a.records[0],'one/value')['state'],'conflicting_cells_for_route')
 def test_formula_cache_and_duplicate_visit_rejected(self):
  w,h=fixture(['Count'],[7],[('g/count','Count',9)]);w['tables'][0]['formula_cells_using_cached_values']=1
  with self.assertRaises(ValueError):FlatAnswers(w,h)
  w['tables'][0]['formula_cells_using_cached_values']=0;w['tables'][0]['rows'].append(copy.deepcopy(w['tables'][0]['rows'][0]))
  with self.assertRaises(ValueError):FlatAnswers(w,h)
 def test_unknown_headers_are_accounted_for(self):
  w,h=fixture(['New question'],['new'],[('g/count','Count',9)]);a=FlatAnswers(w,h);self.assertIn('New question',a.coverage()['forms']['form']['unmapped_headers']);self.assertEqual(a.query(a.records[0],'g/count')['state'],'route_not_mapped')

if __name__=='__main__':unittest.main()
