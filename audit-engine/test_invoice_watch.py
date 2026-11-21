import copy,json,shutil,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import engine,invoice_adapter,invoice_pipeline,invoice_watch
from test_invoice_pipeline import fixture_book
from test_invoices import SCOPE,POLICY

class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.originals=self.root/'originals';self.originals.mkdir();self.source=self.root/'current.json';self.policy=self.root/'policy.json';self.policy.write_text(engine.canonical(POLICY),encoding='utf-8');self.runtime=self.root/'runtime'
  self.first=self.prepare('first',53.33);self.second=self.prepare('second',54.33);self.third=self.prepare('third',55.33);self.initial=self.root/'initial.json';self.initial.write_bytes(self.first);self.source.write_bytes(self.second)
 def tearDown(self):self.temp.cleanup()
 def prepare(self,name,amount,scope=None):
  book=self.originals/(name+'.xlsx');fixture_book(book,amount);return engine.canonical(invoice_adapter.workbook_cut(book,scope or SCOPE)).encode('utf-8')
 def observer(self):return invoice_watch.InvoiceObserver(self.source,self.policy,self.runtime,self.originals,self.initial)
 def latest(self):
  with engine.Engine(self.runtime) as e:return json.loads(e.db.execute("SELECT event_json FROM events WHERE json_extract(event_json,'$.action')='invoice.observer.accepted' ORDER BY seq DESC LIMIT 1").fetchone()[0])['payload']
 def test_new_cut_compares_previous_acceptance_and_reuses_unchanged(self):
  o=self.observer();first=o.poll();self.assertEqual(first['status'],'healthy');self.assertEqual(self.latest()['reference_snapshot'],engine.sha(self.first))
  again=o.poll();self.assertTrue(again['reused']);self.assertEqual(again['run_id'],first['run_id'])
  self.source.write_bytes(self.third);last=o.poll();self.assertEqual(last['status'],'healthy');self.assertEqual(self.latest()['reference_snapshot'],engine.sha(self.second));self.assertEqual(last['coverage']['matched_unique_keys'],1)
  with engine.Engine(self.runtime) as e:self.assertEqual(e.db.execute('SELECT count(*) FROM runs').fetchone()[0],2)
 def test_restart_and_policy_change_keep_original_comparison_pair(self):
  self.observer().poll();o=self.observer();again=o.poll();self.assertTrue(again['reused'])
  self.policy.write_text(engine.canonical(POLICY|{'version':'test/2'}),encoding='utf-8');changed=o.poll();self.assertEqual(changed['status'],'healthy');self.assertFalse(changed['reused']);self.assertEqual(self.latest()['reference_snapshot'],engine.sha(self.first))
 def test_bad_source_cannot_advance_cursor(self):
  o=self.observer();accepted=o.poll();self.source.write_bytes(b'{broken');bad=o.poll();self.assertEqual(bad['status'],'degraded');self.assertEqual(bad['last_accepted']['snapshot'],accepted['snapshot'])
  o.poll()
  with engine.Engine(self.runtime) as e:
   n=e.db.execute('SELECT count(*) FROM events').fetchone()[0];self.assertEqual(n,3)
  self.source.write_bytes(self.second);self.assertEqual(o.poll()['status'],'healthy');self.source.write_bytes(b'{broken');o.poll()
  with engine.Engine(self.runtime) as e:self.assertEqual(e.db.execute('SELECT count(*) FROM events').fetchone()[0],4)
 def test_scope_change_starts_its_own_lineage(self):
  o=self.observer();o.poll();new_scope=copy.deepcopy(SCOPE);new_scope['cohort_id']='different-panel';different=self.prepare('different',56,scope=new_scope);self.source.write_bytes(different);new=o.poll();self.assertEqual(new['status'],'healthy');self.assertFalse(new['coverage']['comparison_requested']);self.assertIsNone(self.latest()['reference_snapshot'])
  self.source.write_bytes(self.third);old=o.poll();self.assertEqual(old['status'],'healthy');self.assertEqual(self.latest()['reference_snapshot'],engine.sha(self.second))
 def test_capture_bytes_before_producer_replaces_file(self):
  o=self.observer();original=invoice_pipeline.execute
  def replacement(*a,**kw):self.source.write_bytes(self.third);return original(*a,**kw)
  with patch('invoice_watch.invoice_pipeline.execute',side_effect=replacement):result=o.poll()
  self.assertEqual(result['snapshot'],engine.sha(self.second));self.assertEqual(self.latest()['snapshot'],engine.sha(self.second))
  next_=o.poll();self.assertEqual(next_['snapshot'],engine.sha(self.third));self.assertEqual(self.latest()['reference_snapshot'],engine.sha(self.second))
 def test_only_one_observer_owns_a_runtime(self):
  with invoice_watch.observer_lock(self.runtime):
   with self.assertRaises(RuntimeError):
    with invoice_watch.observer_lock(self.runtime):pass
 def test_original_path_cannot_escape_allowed_directory(self):
  cut=json.loads(self.second);cut['provenance']['filename']='../outside.xlsx';self.source.write_text(engine.canonical(cut),encoding='utf-8');result=self.observer().poll();self.assertEqual(result['status'],'degraded')
  with engine.Engine(self.runtime) as e:self.assertEqual(e.db.execute('SELECT count(*) FROM runs').fetchone()[0],0)
 def test_adapter_reads_the_same_bytes_it_hashes(self):
  book=self.originals/'second.xlsx';raw=book.read_bytes();book.write_bytes(b'producer replaced original');cut=invoice_adapter.workbook_cut(book,SCOPE,raw=raw);self.assertEqual(cut['provenance']['original_sha256'],engine.sha(raw))

if __name__=='__main__':unittest.main()
