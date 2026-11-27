import json,unittest
from unittest.mock import patch
import engine,supervisor,sync_outbox_watch
import test_sync_outbox as fixtures

class ObserverTests(unittest.TestCase):
 def setUp(self):
  self.f=fixtures.OutboxTests();self.f.setUp();self.addCleanup(self.f.tearDown);self.o=self.observer()
 def observer(self):return sync_outbox_watch.Observer(self.f.invoice,self.f.scan,self.f.lineage,self.f.outbox,'https://audit.example.org','appgprj_fixture')
 def test_unchanged_inputs_do_not_rebuild_or_duplicate_receipts_and_restart_recovers(self):
  with patch('sync_outbox_watch.sync_outbox.prepare',wraps=sync_outbox_watch.sync_outbox.prepare) as prepare:
   a=self.o.poll();b=self.o.poll();self.assertEqual(prepare.call_count,1)
  self.assertEqual(a['status'],'healthy');self.assertEqual(a['delivery'],'not_configured');self.assertEqual(a['state'],'prepared_not_sent');self.assertEqual(a['run_id'],b['run_id'])
  restarted=self.observer().poll();self.assertEqual(restarted['run_id'],a['run_id'])
  with engine.Engine(self.f.outbox) as e:
   events=[json.loads(r[0]) for r in e.db.execute('SELECT event_json FROM events')];self.assertEqual(sum(r['action']=='outbox.observer.prepared' for r in events),1);self.assertTrue(e.verify())
 def test_new_source_waits_for_lineage_and_then_prepares_new_package(self):
  first=self.o.poll();self.f.scan_data['envios'][0]['codigoTienda']='changed-store';self.f.write_scan();bad=self.o.poll();self.assertEqual(bad['status'],'degraded');self.assertEqual(bad['last_accepted']['run_id'],first['run_id'])
  self.f.make_lineage();good=self.o.poll();self.assertEqual(good['status'],'healthy');self.assertNotEqual(good['run_id'],first['run_id'])
 def test_cached_sources_are_verified_and_corruption_preserves_last_package(self):
  first=self.o.poll();(self.f.scan/'objects'/(self.f.scan_run['snapshot']+'.json')).write_bytes(b'changed')
  bad=self.o.poll();self.assertEqual(bad['status'],'degraded');self.assertEqual(bad['last_accepted']['run_id'],first['run_id'])
 def test_cached_output_custody_corruption_is_not_shown_as_healthy(self):
  first=self.o.poll();_,m=self.f.accepted();h=m['artifacts']['invoice.reference.current_workbook']['sha256'];(self.f.outbox/'objects'/(h+'.xlsx')).write_bytes(b'changed')
  bad=self.o.poll();self.assertEqual(bad['status'],'degraded');self.assertFalse(bad['outbox_custody_verified']);self.assertEqual(bad['last_accepted']['run_id'],first['run_id'])
 def test_missing_previously_accepted_database_is_degraded(self):
  first=self.o.poll();path=self.f.outbox/'audit.sqlite';backup=path.with_suffix('.saved');path.rename(backup)
  try:
   bad=self.o.poll();self.assertEqual(bad['status'],'degraded');self.assertFalse(bad['outbox_custody_verified']);self.assertEqual(bad['last_accepted']['run_id'],first['run_id'])
  finally:backup.rename(path)
  self.assertEqual(self.o.poll()['status'],'healthy')
 def test_failed_receipt_is_recovered_from_durable_package_on_restart(self):
  with patch.object(self.o,'receipt',side_effect=OSError('Synthetic receipt failure')):self.assertEqual(self.o.poll()['status'],'degraded')
  recovered=self.observer().poll();self.assertEqual(recovered['status'],'healthy')
  with engine.Engine(self.f.outbox) as e:self.assertEqual(e.db.execute('SELECT count(*) FROM runs').fetchone()[0],1)
 def test_duplicate_watch_and_interval_bounds(self):
  for interval in [True,0,29,3601]:
   with self.assertRaises(ValueError):sync_outbox_watch.watch(self.o,interval,1)
  with supervisor.exclusive(self.f.outbox/'outbox-observer.lock'):
   with self.assertRaises(RuntimeError):sync_outbox_watch.watch(self.o,60,1)
 def jobs(self):
  f=self.f;p=f.root
  return [{'name':'scan','kind':'scan','source':str(f.scan_source),'policy':str(p/'scan-policy.json'),'runtime':str(f.scan),'interval':10},
   {'name':'invoice','kind':'invoice','source':str(f.source),'policy':str(f.policy),'originals':str(p/'originals'),'runtime':str(f.invoice),'interval':10},
   {'name':'lineage','kind':'lineage','invoice_runtime':str(f.invoice),'scan_runtime':str(f.scan),'kpi_dir':str(f.kpi),'perfect_store_dir':str(f.ps),'runtime':str(f.lineage),'report':str(p/'lineage.html'),'interval':10},
   {'name':'outbox','kind':'outbox','invoice_runtime':str(f.invoice),'scan_runtime':str(f.scan),'lineage_runtime':str(f.lineage),'runtime':str(f.outbox),'origin':'https://audit.example.org','project_id':'appgprj_fixture','interval':60}]
 def validate(self,jobs):
  path=self.f.root/'supervisor.json';supervisor.atomic(path,{'schema':'mindtec-supervisor/1','jobs':jobs});return supervisor.config_file(path)
 def test_supervisor_pins_command_and_reports_prepared_not_delivered(self):
  jobs=self.jobs();self.validate(jobs);args=supervisor.command(jobs[-1]);self.assertTrue(args[1].endswith('sync_outbox_watch.py'));self.assertIn('--origin',args);self.assertIn('--project-id',args)
  h=self.o.poll();s=supervisor.health(jobs[-1],h['pid']);self.assertEqual(s['status'],'healthy');self.assertEqual(s['state'],'prepared_not_sent');self.assertEqual(s['delivery'],'not_configured')
 def test_supervisor_rejects_unbound_mismatched_or_overlapping_custody(self):
  jobs=self.jobs()
  with self.assertRaisesRegex(ValueError,'configured invoice'):self.validate([j for j in jobs if j['kind']!='invoice'])
  jobs=self.jobs();jobs[2]['scan_runtime']=str(self.f.root/'other-scan')
  with self.assertRaisesRegex(ValueError,'same source'):self.validate(jobs)
  jobs=self.jobs();jobs[-1]['runtime']=str(self.f.scan/'nested')
  with self.assertRaises(ValueError):self.validate(jobs)
  jobs=self.jobs();jobs[-1]['origin']='https://user:secret@audit.example.org'
  with self.assertRaises(ValueError):self.validate(jobs)

if __name__=='__main__':unittest.main()
