import copy,io,json,tempfile,unittest,zipfile
from pathlib import Path
from xml.sax.saxutils import escape
import engine,collection_watch,collection_adapter
from test_collection_audit import cut,setcell

def xlsx(data):
 out=io.BytesIO();ns='http://schemas.openxmlformats.org/spreadsheetml/2006/main';rel='http://schemas.openxmlformats.org/officeDocument/2006/relationships'
 with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
  z.writestr('xl/workbook.xml','<workbook xmlns="'+ns+'" xmlns:r="'+rel+'"><sheets>'+''.join('<sheet name="'+escape(t['sheet'])+'" sheetId="'+str(i)+'" r:id="r'+str(i)+'"/>' for i,t in enumerate(data['tables'],1))+'</sheets></workbook>')
  z.writestr('xl/_rels/workbook.xml.rels','<Relationships>'+''.join('<Relationship Id="r'+str(i)+'" Target="worksheets/sheet'+str(i)+'.xml"/>' for i in range(1,6))+'</Relationships>')
  for i,t in enumerate(data['tables'],1):
   rows=[{'source_row':1,'cells':t['headers']}]+t['rows'];parts=[]
   for row in rows:
    number=row['source_row'];cells=[]
    for j,value in enumerate(row['cells']):
     if value is None:continue
     coord=chr(65+j)+str(number)
     cells.append('<c r="'+coord+'"><v>'+str(value)+'</v></c>' if isinstance(value,(int,float)) else '<c r="'+coord+'" t="inlineStr"><is><t>'+escape(str(value))+'</t></is></c>')
    parts.append('<row r="'+str(number)+'">'+''.join(cells)+'</row>')
   z.writestr('xl/worksheets/sheet'+str(i)+'.xml','<worksheet xmlns="'+ns+'"><sheetData>'+''.join(parts)+'</sheetData></worksheet>')
 return out.getvalue()

class WatchTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.root=Path(self.tmp.name)
  self.source=self.root/'selected.xlsx';self.policy=self.root/'policy.json';self.crosswalk=self.root/'crosswalk.json';self.runtime=self.root/'runtime';self.reference=self.root/'reference.xlsx'
  self.data=cut();self.source.write_bytes(xlsx(self.data));self.reference.write_bytes(xlsx(self.data))
  self.policy.write_text(json.dumps({'schema':'mindtec-audit-policy/1','version':'1','exclusions':[]}));self.crosswalk.write_text(json.dumps({'rows':[{'internal_id':'1','kobo_id':'101'}]}));self.o=self.observer()
 def observer(self):return collection_watch.Observer(self.source,self.policy,self.crosswalk,self.runtime,self.reference)
 def count(self):
  with engine.Engine(self.runtime) as e:return e.db.execute('SELECT count(*) FROM runs').fetchone()[0]
 def test_accepts_real_xlsx_and_restarts_idempotently(self):
  a=self.o.poll();self.assertEqual(a['status'],'healthy');self.assertEqual(a['coverage']['exported_visits'],1);self.assertFalse(a['network_delivery']);self.assertEqual(self.observer().poll()['run_id'],a['run_id']);self.assertEqual(self.count(),1)
 def test_next_cut_uses_retained_prior_not_mutable_initial_reference(self):
  a=self.o.poll();self.reference.write_bytes(b'changed after acceptance');setcell(self.data,'prices','Precio Bs',9);self.source.write_bytes(xlsx(self.data));b=self.o.poll();self.assertEqual(b['status'],'healthy');self.assertNotEqual(a['run_id'],b['run_id']);prior=self.o.prior();self.assertEqual(prior['result']['numeric_change_statistics']['prices:Precio Bs']['bias_after_minus_before'],4)
 def test_invalid_candidate_does_not_advance_and_is_retained_once(self):
  a=self.o.poll();self.source.write_bytes(b'partial write');b=self.o.poll();self.assertEqual(b['status'],'degraded');self.assertEqual(b['last_accepted']['run_id'],a['run_id']);self.o.poll();self.assertEqual(self.count(),1)
  with engine.Engine(self.runtime) as e:
   self.assertEqual(sum(json.loads(r[0])['action']=='collection.observer.rejected' for r in e.db.execute('SELECT event_json FROM events')),1)
   self.assertTrue(any((e.root/r[0]).read_bytes()==b'partial write' for r in e.db.execute('SELECT object_path FROM snapshots')))
 def test_policy_change_recalculates_with_same_comparison_reference(self):
  a=self.o.poll();self.policy.write_text(json.dumps({'schema':'mindtec-audit-policy/1','version':'2','exclusions':[{'id':'101','reason':'documented'}]}));b=self.o.poll();self.assertEqual(b['status'],'healthy');self.assertNotEqual(a['run_id'],b['run_id']);self.assertEqual(b['coverage']['historical_policy_eligible_visits'],0);self.assertFalse(self.o.prior()['rules']['data_changed'])
 def test_duplicate_crosswalk_and_missing_headers_fail_closed(self):
  a=self.o.poll();self.crosswalk.write_text(json.dumps({'rows':[{'internal_id':'1','kobo_id':'101'},{'internal_id':'1','kobo_id':'102'}]}));self.assertEqual(self.o.poll()['status'],'degraded');self.assertEqual(self.count(),1)
  self.crosswalk.write_text(json.dumps({'rows':[{'internal_id':'1','kobo_id':'101'}]}));self.data['tables'][2]['headers'][-1]='Wrong';self.source.write_bytes(xlsx(self.data));b=self.o.poll();self.assertEqual(b['status'],'degraded');self.assertEqual(b['last_accepted']['run_id'],a['run_id'])
 def test_empty_visit_export_is_not_new_accepted_cut(self):
  a=self.o.poll();self.data['tables'][0]['rows']=[];self.source.write_bytes(xlsx(self.data));b=self.o.poll();self.assertEqual(b['status'],'degraded');self.assertEqual(self.count(),1)
 def test_custody_corruption_is_not_reported_healthy(self):
  self.o.poll()
  with engine.Engine(self.runtime) as e:
   row=e.db.execute('SELECT object_path FROM snapshots LIMIT 1').fetchone();(e.root/row[0]).write_bytes(b'corrupted')
  b=self.o.poll();self.assertEqual(b['status'],'degraded');self.assertFalse(b['custody_verified']);self.assertTrue(b['failure_history_unverified'])
 def test_source_namespace_and_unsafe_runtime_are_not_guessed(self):
  with self.assertRaises(ValueError):collection_watch.Observer(self.source,self.policy,self.crosswalk,self.root)
  self.o.poll();other=collection_watch.Observer(self.root/'other.xlsx',self.policy,self.crosswalk,self.runtime,self.reference);self.assertEqual(other.poll()['status'],'degraded')
 def test_exclusive_observer_lock(self):
  with collection_watch.supervisor.exclusive(self.runtime/'collection-observer.lock'):
   with self.assertRaises(RuntimeError):collection_watch.watch(self.o,30,1)
 def test_formula_cache_rejected(self):
  c=collection_adapter.workbook_tables(self.source);c['tables'][0]['formula_cells_using_cached_values']=1
  with self.assertRaises(ValueError):collection_watch.validate(c)

if __name__=='__main__':unittest.main()
