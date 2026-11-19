import json
from pathlib import Path
import unittest
from unittest.mock import patch
import engine
import data_quality_watch as watch
import data_quality_run
import test_data_quality_run as fixture


class Tests(unittest.TestCase):
    def setUp(self):
        self.f=fixture.Tests();self.f.setUp();self.addCleanup(self.f.doCleanups);self.f.prepare();self.root=self.f.root
        self.catalogue=self.root/'catalogue.csv';self.catalogue.write_text('Código en Kobo;Marca\nsku_1;A\n',encoding='utf-8');self.pin=engine.sha(self.catalogue.read_bytes());self.runtime=self.root/'observed'

    def observer(self):return watch.Observer(self.f.invoice,self.catalogue,self.pin,self.runtime)

    def test_accept_recover_and_reuse_without_duplicate_runs_or_events(self):
        first=self.observer().poll();self.assertEqual(first['status'],'healthy');second=self.observer().poll();self.assertEqual(second['state'],'verified_unchanged');self.assertEqual(first['run_id'],second['run_id'])
        with engine.Engine(self.runtime) as e:
            self.assertEqual(e.db.execute('SELECT count(*) FROM runs').fetchone()[0],1)
            self.assertEqual(e.db.execute("SELECT count(*) FROM events WHERE json_extract(event_json,'$.action')='data_quality.observer.accepted'").fetchone()[0],1)

    def test_changed_catalogue_preserves_acceptance_and_deduplicates_rejection(self):
        o=self.observer();first=o.poll();self.catalogue.write_bytes(b'changed');bad=o.poll();self.assertEqual(bad['status'],'degraded');self.assertEqual(bad['last_accepted']['run_id'],first['run_id']);o.poll()
        with engine.Engine(self.runtime) as e:
            self.assertEqual(e.db.execute("SELECT count(*) FROM events WHERE json_extract(event_json,'$.action')='data_quality.observer.rejected'").fetchone()[0],1)
        self.assertTrue(data_quality_run.verify(self.runtime,first['run_id'])['custody_verified'])

    def test_different_binding_is_rejected_on_restart(self):
        self.observer().poll();other=self.root/'other.csv';other.write_bytes(self.catalogue.read_bytes());bad=watch.Observer(self.f.invoice,other,self.pin,self.runtime).poll();self.assertEqual(bad['status'],'degraded')

    def test_changed_source_during_calculation_does_not_promote(self):
        source=watch.source_execution(self.f.invoice)
        with patch.object(watch,'source_execution',side_effect=[source,{'run_id':'other','snapshot_sha256':'changed'}]):bad=self.observer().poll()
        self.assertEqual(bad['status'],'degraded');self.assertIsNone(bad['last_accepted'])
        with engine.Engine(self.runtime) as e:
            self.assertEqual(e.db.execute("SELECT count(*) FROM events WHERE json_extract(event_json,'$.action')='data_quality.observer.accepted'").fetchone()[0],0)

    def test_pinned_catalogue_change_during_calculation_does_not_promote(self):
        original=data_quality_run.execute
        def mutate(*args):
            result=original(*args);self.catalogue.write_bytes(b'changed');return result
        with patch.object(watch.runner,'execute',side_effect=mutate):bad=self.observer().poll()
        self.assertEqual(bad['status'],'degraded');self.assertIsNone(bad['last_accepted'])

    def test_invalid_paths_pin_and_loaded_code_are_rejected(self):
        for source,catalogue,pin,runtime in [(self.f.invoice,self.catalogue,'bad',self.runtime),(self.f.invoice,self.catalogue,self.pin,self.f.invoice/'nested'),(self.f.invoice,self.f.invoice/'cat.csv',self.pin,self.runtime)]:
            with self.assertRaises(ValueError):watch.Observer(source,catalogue,pin,runtime)
        with patch.dict(watch.LOADED,{'data_quality_watch.py':b'changed'}):self.assertEqual(self.observer().poll()['status'],'degraded')

    def test_bounded_watch_is_exclusive_and_reports_stopped(self):
        o=self.observer()
        with watch.supervisor.exclusive(self.runtime/'quality-observer.lock'):
            with self.assertRaises(RuntimeError):watch.watch(o,iterations=1)
        watch.watch(o,iterations=1);h=json.loads((self.runtime/'health.json').read_text());self.assertEqual(h['status'],'stopped');self.assertEqual(h['last_poll_status'],'healthy');self.assertFalse(h['observer_running'])


if __name__=='__main__':unittest.main()
