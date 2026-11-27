import json,unittest
from unittest.mock import patch
import engine,supervisor,sync_client,sync_delivery_watch
import test_sync_client as fixtures
import test_sync_outbox_watch as outbox_fixtures

class PublisherTests(unittest.TestCase):
 def setUp(self):
  self.f=fixtures.ClientTests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.clock=0;self.credential='synthetic-service-token';self.o=self.observer()
 def observer(self):return sync_delivery_watch.Observer(self.f.path,300,3600,transport=self.f.site,credential_provider=lambda c:self.credential,clock=lambda:self.clock)
 def test_new_delivery_cached_poll_and_periodic_readback_have_distinct_states(self):
  first=self.o.poll();self.assertEqual(first['state'],'delivered_verified');self.assertTrue(first['remote_verified_this_poll']);posts=len(self.f.site.posts)
  self.clock=300
  with patch.object(self.f.site,'get',wraps=self.f.site.get) as get:
   cached=self.o.poll();self.assertEqual(get.call_count,0)
  self.assertEqual(cached['state'],'unchanged_package_local_receipt_verified');self.assertFalse(cached['remote_verified_this_poll']);self.assertEqual(cached['last_remote_check_at'],first['last_remote_check_at'])
  self.clock=3600
  with patch.object(self.f.site,'get',wraps=self.f.site.get) as get:
   live=self.o.poll();self.assertEqual(get.call_count,1)
  self.assertTrue(live['remote_verified_this_poll']);self.assertEqual(len(self.f.site.posts),posts);self.assertEqual(self.f.count(),1)
 def test_new_package_is_delivered_before_periodic_recheck(self):
  self.o.poll();old=self.o.last_accepted['local_package_run_id'];self.f.f.scan_data['envios'][0]['codigoTienda']='changed';self.f.f.write_scan();self.f.f.make_lineage();self.f.f.prepare();self.clock=300
  result=self.o.poll();self.assertEqual(result['status'],'healthy');self.assertNotEqual(result['last_accepted']['local_package_run_id'],old);self.assertEqual(self.f.count(),2)
 def test_missing_credential_preserves_receipt_and_never_uses_cached_success_as_access(self):
  first=self.o.poll();self.credential=None;self.clock=300
  with patch.object(self.f.site,'get',wraps=self.f.site.get) as get:
   bad=self.o.poll();self.assertEqual(get.call_count,0)
  self.assertEqual(bad['status'],'degraded');self.assertFalse(bad['remote_verified_this_poll']);self.assertEqual(bad['last_accepted']['run_id'],first['last_accepted']['run_id']);self.assertIn('credential',bad['reason'])
  self.clock=301;self.assertEqual(self.o.poll()['state'],'waiting_retry')
 def test_retry_after_postpones_network_and_then_recovers(self):
  self.o.poll();self.clock=3600
  with patch.object(self.f.site,'get',side_effect=sync_client.SyncError('rate_limited',429,900)) as get:
   failed=self.o.poll();self.assertEqual(failed['retry_in_seconds'],900);self.assertEqual(get.call_count,1);self.clock=3900;self.assertEqual(self.o.poll()['state'],'waiting_retry');self.assertEqual(get.call_count,1)
  self.clock=4500;self.assertEqual(self.o.poll()['state'],'delivered_verified');self.assertEqual(self.f.count(),1)
 def test_restart_recovers_receipt_but_requires_fresh_remote_readback(self):
  first=self.o.poll();restarted=self.observer()
  with patch.object(self.f.site,'get',wraps=self.f.site.get) as get:
   result=restarted.poll();self.assertEqual(get.call_count,1)
  self.assertTrue(result['remote_verified_this_poll']);self.assertEqual(result['last_accepted']['run_id'],first['last_accepted']['run_id']);self.assertEqual(self.f.count(),1)
 def test_corrupt_local_delivery_is_degraded_even_on_unchanged_package(self):
  self.o.poll();root=self.o.runtime
  with engine.Engine(root) as e:
   row=e.db.execute('SELECT snapshot_hash FROM runs ORDER BY at DESC LIMIT 1').fetchone();obj=e.db.execute('SELECT object_path FROM snapshots WHERE hash=?',(row[0],)).fetchone()[0]
  (root/obj).write_bytes(b'changed');self.clock=300;result=self.o.poll();self.assertEqual(result['status'],'degraded');self.assertFalse(result['local_delivery_custody_verified']);self.assertTrue(result['failure_history_unverified'])
 def test_config_change_and_duplicate_watcher_are_rejected(self):
  with supervisor.exclusive(self.o.runtime/'sync-publisher.lock'):
   with self.assertRaises(RuntimeError):sync_delivery_watch.watch(self.o,1)
  self.f.c['origin']='https://other.example.org';self.f.save();result=self.o.poll();self.assertEqual(result['status'],'degraded');self.assertEqual(result['reason'],'configuration_changed_restart_required');self.assertEqual(self.f.site.posts,[])
 def jobs(self):
  helper=outbox_fixtures.ObserverTests();helper.f=self.f.f;jobs=helper.jobs();jobs.append({'name':'publisher','kind':'publisher','config':str(self.f.path),'runtime':str(self.o.runtime),'interval':300,'recheck_interval':3600});return jobs
 def validate(self,jobs):
  path=self.f.f.root/'supervisor-publisher.json';supervisor.atomic(path,{'schema':'mindtec-supervisor/1','jobs':jobs});return supervisor.config_file(path)
 def test_supervisor_pins_scope_and_does_not_claim_credentials_exist(self):
  jobs=self.jobs()
  with patch.dict('os.environ',{},clear=True):self.validate(jobs)
  args=supervisor.command(jobs[-1]);self.assertTrue(args[1].endswith('sync_delivery_watch.py'));self.assertIn('--recheck-interval',args);self.assertNotIn('--token',args)
  result=self.o.poll();state=supervisor.health(jobs[-1],result['pid']);self.assertTrue(state['remote_verified_this_poll']);self.assertEqual(state['state'],'delivered_verified')
 def test_supervisor_rejects_unbound_or_disabled_publisher(self):
  jobs=self.jobs()
  with self.assertRaises(ValueError):self.validate([j for j in jobs if j['kind']!='outbox'])
  self.f.c['enabled']=False;self.f.save()
  with self.assertRaises(ValueError):self.validate(jobs)

class RetryAfterTests(unittest.TestCase):
 def test_bounded_retry_after_seconds_and_http_date(self):
  self.assertEqual(sync_client.retry_after('900'),900);self.assertEqual(sync_client.retry_after('Thu, 01 Jan 1970 00:10:00 GMT',now=0),600);self.assertEqual(sync_client.retry_after('Thu, 01 Jan 1970 00:10:00 GMT',now=1000),0)
  for value in [None,'secret-bearing-invalid-value','9'*129,'-1']:self.assertIsNone(sync_client.retry_after(value))

if __name__=='__main__':unittest.main()
