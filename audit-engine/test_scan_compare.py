import copy,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import engine,scan_compare

def row(id='1',month='2026-09',form='survey',answers=None,**extra):
 return {'envioKobo':id,'formulario':form,'fechaVisita':month+'-15T12:00:00Z','respuestas':answers or [],**extra}
def cut(*rows):return {'total':len(rows),'envios':list(rows)}
def compare(a,b,months=None):return scan_compare.compare([a],[b],months or ['2026-09'])

class ComparisonTests(unittest.TestCase):
 def test_partial_month_export_cannot_be_misread_as_deletions(self):
  old=cut(row(),row('2','2026-10'));new=cut(row())
  with self.assertRaisesRegex(ValueError,'month absent'):compare(old,new,['2026-09','2026-10'])
  result=compare(old,new);self.assertEqual(result['findings'],[]);self.assertEqual(result['summary']['matched_records'],1)
 def test_adding_or_omitting_an_identity_is_observed_without_deletion_claim(self):
  result=compare(cut(row(),row('2')),cut(row(),row('3')))
  self.assertEqual(result['summary']['findings_by_rule'],{'record_absent':1,'record_added':1})
  self.assertFalse(result['summary']['scope_complete_declared']);self.assertTrue(all(f['disposition']=='needs_human_review' for f in result['findings']))
 def test_equal_kobo_id_in_different_forms_is_never_fuzzy_joined(self):
  result=compare(cut(row()),cut(row(form='other')))
  self.assertEqual(result['summary']['matched_records'],0);self.assertEqual(len(result['findings']),2)
 def test_duplicate_record_keys_do_not_choose_a_winner(self):
  result=compare(cut(row(),row(answers=[{'ruta':'a','valor':1}])),cut(row()))
  self.assertEqual(result['summary']['ambiguous_record_keys'],1);self.assertEqual(result['summary']['matched_records'],0)
  self.assertEqual(result['findings'][0]['rule'],'ambiguous_record_key');self.assertEqual(len(result['findings'][0]['evidence']['previous_rows']),2)
 def test_missing_null_zero_and_text_are_distinct_and_paths_resolve(self):
  old=cut(row(answers=[{'ruta':'a','valor':0},{'ruta':'b','valor':None}],revision=None))
  new=cut(row(answers=[{'ruta':'a','valor':'0'}]))
  result=compare(old,new);rules=result['summary']['findings_by_rule'];self.assertEqual(rules,{'record_field_changed':1,'answer_changed':2})
  meta=next(f for f in result['findings'] if f['rule']=='record_field_changed');self.assertTrue(meta['evidence']['previous']['present']);self.assertFalse(meta['evidence']['current']['present'])
  for f in result['findings']:
   ev=f['evidence'];self.assertEqual(ev['previous_row']['row'],0)
   if f['rule']=='answer_changed':
    for reference in ev['previous']:self.assertEqual(old['envios'][0]['respuestas'][reference['answer_index']],reference['answer'])
 def test_duplicate_answer_path_is_uncertainty_not_confirmed_change(self):
  data=cut(row(answers=[{'ruta':'a','valor':1},{'ruta':'a','valor':1}]))
  result=compare(data,data);self.assertEqual(result['summary']['changed_records'],0);self.assertEqual(result['summary']['unchanged_records'],0);self.assertEqual(result['summary']['records_with_ambiguous_answers'],1)
 def test_month_movement_is_not_an_unrelated_addition_or_absence(self):
  old=cut(row('moving','2026-09'),row('stable','2026-10'));new=cut(row('moving','2026-10'),row('stable','2026-10'),row('sep','2026-09'))
  result=compare(old,new);rules=result['summary']['findings_by_rule'];self.assertEqual(rules['record_moves_across_scope'],1);self.assertNotIn('record_absent',rules)
 def test_invalid_dates_empty_scope_and_duplicate_months_rejected(self):
  for months in [[],['2026-09','2026-09'],['2026-13']]:
   with self.subTest(months=months),self.assertRaises(ValueError):scan_compare.compare([cut(row())],[cut(row())],months)
  with self.assertRaisesRegex(ValueError,'Valid visit date'):compare(cut(row(fechaVisita='not a date')),cut(row()))
 def test_multiple_input_files_are_retained_and_repeat_is_idempotent(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);old=root/'old.json';sep=root/'sep.json';oct=root/'oct.json';runtime=root/'custody'
   values={old:cut(row(),row('2','2026-10')),sep:cut(row()),oct:cut(row('2','2026-10',revision='REVISADA'))}
   originals={p:engine.canonical(v).encode() for p,v in values.items()}
   for path,raw in originals.items():path.write_bytes(raw)
   first=scan_compare.run([old],[sep,oct],['2026-09','2026-10'],runtime);second=scan_compare.run([old],[sep,oct],['2026-10','2026-09'],runtime)
   self.assertEqual(first['run_id'],second['run_id']);self.assertTrue(second['reused'])
   sep.write_text('replaced after acceptance',encoding='utf-8')
   with engine.Engine(runtime) as e:
    self.assertTrue(e.verify());rules=json.loads(e.db.execute('SELECT rules_json FROM runs').fetchone()[0]);self.assertEqual(rules['reference_sources']['current_0'],engine.sha(originals[sep]))
    self.assertEqual(e.db.execute('SELECT count(*) FROM runs').fetchone()[0],1)
 def test_implementation_change_prevents_acceptance(self):
  with patch.object(scan_compare,'IMPLEMENTATION_BYTES',b'wrong'):
   with self.assertRaisesRegex(ValueError,'Implementation changed'):scan_compare.run(['a'],['b'],['2026-09'],'unused-runtime')

if __name__=='__main__':unittest.main()
