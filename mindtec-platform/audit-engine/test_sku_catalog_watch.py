import json
import base64
import unittest
from unittest.mock import patch

import sku_catalog_watch as watch
import supervisor
import test_sku_catalog_run


class CatalogObserverTests(unittest.TestCase):
    def setUp(self):
        fixture = test_sku_catalog_run.CatalogCustodyTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.source = fixture.workbook
        self.catalog = fixture.catalog
        self.runtime = fixture.root / 'observer'
        self.observer = watch.Observer(self.source, self.catalog, self.runtime)

    def test_first_then_reuse(self):
        first = self.observer.poll()
        second = self.observer.poll()
        self.assertEqual(first['state'], 'new_cut_accepted')
        self.assertEqual(second['state'], 'verified_unchanged')
        self.assertEqual(len(list((self.runtime / 'runs').iterdir())), 1)

    def test_invalid_new_source_preserves_accepted(self):
        first = self.observer.poll()
        pointer = (self.runtime / 'accepted.json').read_bytes()
        self.catalog.write_bytes(b'invalid')
        health = self.observer.poll()
        self.assertEqual(health['status'], 'degraded')
        self.assertEqual((self.runtime / 'accepted.json').read_bytes(), pointer)
        self.assertEqual(health['last_accepted'], first['last_accepted'])

    def test_corrupt_prior_is_not_verified(self):
        first = self.observer.poll()
        key = first['last_accepted']['context_sha256']
        (self.runtime / 'runs' / key / 'contrast.json').write_bytes(b'{}')
        self.assertFalse(self.observer.poll()['custody_verified'])

    def test_rebinding_rejected(self):
        self.observer.poll()
        another = watch.Observer(self.source.with_name('other.xlsx'), self.catalog, self.runtime)
        self.assertEqual(another.poll()['status'], 'degraded')

    def test_pointer_summary_tampering_rejected(self):
        self.observer.poll()
        path = self.runtime / 'accepted.json'
        value = json.loads(path.read_text(encoding='utf-8'))
        value['summary']['code_occurrences'] = 999
        path.write_text(json.dumps(value), encoding='utf-8')
        self.assertEqual(self.observer.poll()['status'], 'degraded')

    def test_lock_rejects_duplicate_watch(self):
        with supervisor.exclusive(self.runtime / 'sku-catalog-observer.lock'):
            with self.assertRaises(RuntimeError):
                watch.watch(self.observer, iterations=1)

    def test_bounded_watch_marks_stopped(self):
        health = watch.watch(self.observer, iterations=1)
        self.assertEqual(health['status'], 'stopped')
        self.assertEqual(health['last_poll_status'], 'healthy')
        self.assertFalse(health['observer_running'])

    def test_mutation_during_acquisition_cannot_promote(self):
        original = watch.runner.run
        def changed(source, catalog, output):
            self.catalog.write_text('Código en Kobo;Marca;Valor del catálogo\nsku_1;Red Bull;Red Bull 250 ml\n', encoding='utf-8')
            return original(source, catalog, output)
        with patch.object(watch.runner, 'run', side_effect=changed):
            self.assertEqual(self.observer.poll()['status'], 'degraded')
        self.assertFalse((self.runtime / 'accepted.json').exists())

    def test_restart_validates_prior_code_instead_of_current_supervisor_version(self):
        first=self.observer.poll();old_key=first['last_accepted']['context_sha256'];old_dir=self.runtime/'runs'/old_key
        bundle=json.loads((old_dir/'observer-code.json').read_text());historic=b'older observer dependency';bundle['files']['supervisor.py']={'sha256':watch.runner.digest(historic),'content':base64.b64encode(historic).decode()};(old_dir/'observer-code.json').write_bytes(watch.runner.encode(bundle))
        inputs={name:watch.runner.digest((old_dir/name).read_bytes())for name in ('source.xlsx','catalog.csv')}
        historical_key=watch.runner.digest(watch.runner.encode({'binding':self.observer.binding,'inputs':inputs,'implementation':watch.observer_code_hashes(old_dir/'observer-code.json')}));new_dir=self.runtime/'runs'/historical_key;old_dir.rename(new_dir)
        prior={'context_sha256':historical_key,'summary':first['last_accepted']['summary']};supervisor.atomic(self.runtime/'accepted.json',prior)
        restarted=watch.Observer(self.source,self.catalog,self.runtime).poll();self.assertEqual(restarted['status'],'healthy');self.assertEqual(restarted['state'],'new_cut_accepted');self.assertNotEqual(restarted['last_accepted']['context_sha256'],historical_key);self.assertTrue(new_dir.exists())

    def test_retained_observer_code_tampering_is_rejected(self):
        first=self.observer.poll();path=self.runtime/'runs'/first['last_accepted']['context_sha256']/'observer-code.json';bundle=json.loads(path.read_text());bundle['files']['supervisor.py']['content']=base64.b64encode(b'altered').decode();path.write_bytes(watch.runner.encode(bundle));self.assertEqual(self.observer.poll()['status'],'degraded')


if __name__ == '__main__':
    unittest.main()
