import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest

import supervisor
from test_supervisor import Child


class SkuSupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.job = {'kind': 'sku_catalog', 'name': 'sku', 'interval': 60,
                    'workbook': str(self.root / 'source.xlsx'),
                    'catalog': str(self.root / 'catalog.csv'),
                    'runtime': str(self.root / 'runtime')}

    def config(self, jobs=None):
        path = self.root / 'config.json'
        path.write_text(json.dumps({'schema': 'mindtec-supervisor/1',
                                    'jobs': jobs or [self.job]}))
        return supervisor.config_file(path)

    def test_fixed_command_and_valid_config(self):
        self.config()
        args = supervisor.command(self.job)
        self.assertTrue(args[1].endswith('sku_catalog_watch.py'))
        self.assertIn('--workbook', args)
        self.assertIn('--catalog', args)
        self.assertNotIn('--iterations', args)

    def test_fast_polling_rejected(self):
        self.job['interval'] = 30
        with self.assertRaises(ValueError):
            self.config()

    def test_source_cannot_be_inside_other_job_custody(self):
        other = {**self.job, 'name': 'other', 'runtime': str(self.root / 'other')}
        self.job['workbook'] = str(self.root / 'other' / 'source.xlsx')
        with self.assertRaises(ValueError):
            self.config([self.job, other])

    def test_nested_runtimes_rejected(self):
        other = {**self.job, 'name': 'other', 'runtime': str(self.root / 'runtime' / 'nested')}
        with self.assertRaises(ValueError):
            self.config([self.job, other])

    def test_health_exposes_context_and_requires_owned_pid(self):
        now = dt.datetime.now(dt.timezone.utc)
        supervisor.atomic(Path(self.job['runtime']) / 'health.json',
                          {'pid': 101, 'checked_at': now.isoformat(), 'status': 'healthy',
                           'custody_verified': True, 'network_delivery': False,
                           'last_accepted': {'context_sha256': 'a' * 64}})
        self.assertEqual(supervisor.health(self.job, 100, now)['status'], 'awaiting_owned_health')
        health = supervisor.health(self.job, 101, now)
        self.assertEqual(health['context_sha256'], 'a' * 64)
        self.assertTrue(health['custody_verified'])

    def test_stale_health_never_terminates_owned_live_child(self):
        child = Child(101)
        owner = supervisor.Supervisor([self.job], self.root / 'supervision',
                                      spawn=lambda *a, **kw: child)
        self.addCleanup(owner.close)
        owner.tick()
        old = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).isoformat()
        supervisor.atomic(Path(self.job['runtime']) / 'health.json',
                          {'pid': 101, 'checked_at': old, 'status': 'healthy'})
        self.assertEqual(owner.tick()[0]['status'], 'degraded')
        self.assertFalse(child.terminated)


if __name__ == '__main__':
    unittest.main()
