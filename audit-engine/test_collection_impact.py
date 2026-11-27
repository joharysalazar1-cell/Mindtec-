import copy,json,tempfile,unittest
from pathlib import Path
import collection_impact,collection_impact_report,collection_watch,engine
from test_collection_audit import cut,setcell
from test_collection_watch import xlsx

class ImpactTests(unittest.TestCase):
 def test_removed_nonzero_row_changes_subtotal_even_when_common_cells_unchanged(self):
  old=cut(('1','2'));new=cut(('1','2'));new['tables'][2]['rows'].pop()
  r=collection_impact.evaluate(new,old,{'1':'101','2':'102'},{'exclusions':[]})
  self.assertEqual(len(r['presence_changes']),1);self.assertEqual(r['presence_changes'][0]['state'],'only_previous_export');self.assertEqual(r['presence_changes'][0]['cells'][5]['value'],3)
  self.assertEqual(r['category_subtotals'][0]['measures']['Caras en góndola']['registered_subtotal_delta'],-3)
 def test_other_visits_and_exclusions_do_not_turn_into_removals(self):
  r=collection_impact.evaluate(cut(),cut(('1','2')),{'1':'101','2':'102'},{'exclusions':[]});self.assertEqual(r['presence_changes'],[]);self.assertEqual(r['previous_rows_same_current_visits'],1)
  r=collection_impact.evaluate(cut(),cut(),{'1':'101'},{'exclusions':[{'id':'101'}]});self.assertEqual(r['category_subtotals'],[])
 def test_missing_is_counted_not_imputed_and_duplicate_keys_not_paired(self):
  old=cut();new=cut();setcell(new,'brands','Caras en góndola',None);r=collection_impact.evaluate(new,old,{'1':'101'},{'exclusions':[]});m=r['category_subtotals'][0]['measures']['Caras en góndola'];self.assertEqual(m['current']['missing_or_ambiguous_rows'],1);self.assertEqual(m['current']['valid_unambiguous_rows'],0)
  new['tables'][2]['rows'].append(copy.deepcopy(new['tables'][2]['rows'][0]));r=collection_impact.evaluate(new,old,{'1':'101'},{'exclusions':[]});self.assertEqual(r['presence_changes'],[]);self.assertEqual(r['category_subtotals'][0]['measures']['Caras en góndola']['current']['missing_or_ambiguous_rows'],2)
 def test_new_rows_are_traced_to_current_source_and_months_are_separate(self):
  old=cut(('1','2'));new=cut(('1','2'));old['tables'][2]['rows'].pop()
  for c in [old,new]:
   for t in c['tables']:t['rows'][0]['cells'][t['headers'].index('Mes')]='2026-09'
  r=collection_impact.evaluate(new,old,{'1':'101','2':'102'},{'exclusions':[]});self.assertEqual(len(r['category_subtotals']),2);self.assertEqual(r['presence_changes'][0]['month'],'2026-10');self.assertEqual(r['presence_changes'][0]['state'],'only_current_export')
 def test_execute_uses_custody_not_live_inputs_and_reuses_acceptance(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory);old=cut(('1','2'));new=cut(('1','2'));new['tables'][2]['rows'].pop();(p/'old.xlsx').write_bytes(xlsx(old));(p/'new.xlsx').write_bytes(xlsx(new));(p/'policy.json').write_text(engine.canonical({'schema':'mindtec-audit-policy/1','version':'1','exclusions':[]}));(p/'cross.json').write_text(engine.canonical({'rows':[{'internal_id':'1','kobo_id':'101'},{'internal_id':'2','kobo_id':'102'}]}));o=collection_watch.Observer(p/'new.xlsx',p/'policy.json',p/'cross.json',p/'source-runtime',p/'old.xlsx');self.assertEqual(o.poll()['status'],'healthy');(p/'new.xlsx').write_bytes(b'incomplete later input');a=collection_impact.execute(p/'source-runtime',p/'impact-runtime');b=collection_impact.execute(p/'source-runtime',p/'impact-runtime');self.assertEqual(a['run_id'],b['run_id']);self.assertEqual(a['findings'],1)
   with engine.Engine(p/'impact-runtime') as e:self.assertEqual(e.db.execute('SELECT count(*) FROM runs').fetchone()[0],1)
   output=p/'annex.html';summary=collection_impact_report.export(p/'impact-runtime',output);self.assertEqual(summary['registered_shelf_delta'],-3);text=output.read_text(encoding='utf-8');self.assertIn('Solo en el archivo anterior',text);self.assertIn(a['result']['previous_source_sha256'],text)
   with self.assertRaises(FileExistsError):collection_impact_report.export(p/'impact-runtime',output)
 def test_runtime_overlap_rejected(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory)
   with self.assertRaises(ValueError):collection_impact.execute(p,p/'nested')

if __name__=='__main__':unittest.main()
