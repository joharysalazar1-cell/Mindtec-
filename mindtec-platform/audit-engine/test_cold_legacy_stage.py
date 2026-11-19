import json
from pathlib import Path
import unittest
import engine
import collection_watch
import numeric_distribution_run
import cold_share_run
import cold_legacy_stage as stage
import test_perfect_store_watch as fixture


class Tests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.WatchTests(); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.root = self.f.root; self.source = self.root/'cold'; self.output = self.root/'legacy'

    def prepare(self):
        accepted = self.f.o.poll(); numeric_distribution_run.execute(self.f.runtime, self.root/'distribution'); cold_share_run.execute(self.root/'distribution', self.source)
        return accepted

    def test_retains_source_provenance_replays_and_reuses(self):
        accepted = self.prepare(); first = stage.execute(self.source, self.output); second = stage.execute(self.source, self.output)
        self.assertEqual(first['run_id'], second['run_id']); self.assertTrue(stage.verify(self.output)['custody_verified'])
        with engine.Engine(self.output) as e:
            self.assertEqual(e.db.execute('SELECT count(*) FROM runs').fetchone()[0], 1)
            row = e.db.execute('SELECT * FROM runs').fetchone(); result = json.loads(collection_watch.object_bytes(e, row['snapshot_hash']))
            self.assertEqual(result['source_ps_run_id'], accepted['run_id']); self.assertEqual(result['monthly'], [])
            self.assertEqual(set(json.loads(row['rules_json'])['reference_sources']), {'source_cold_result','source_cold_execution','detailed_workbook','implementation'})

    def test_missing_source_or_overlapping_paths_never_create_destination(self):
        with self.assertRaises(ValueError): stage.execute(self.root/'missing', self.output)
        self.assertFalse(self.output.exists()); self.assertFalse((self.root/'missing').exists())
        for output in [self.source, self.source/'nested', self.root]:
            with self.assertRaises(ValueError): stage.execute(self.source, output)

    def test_corrupt_source_is_rejected_before_output(self):
        self.prepare()
        with engine.Engine(self.source) as e:
            p = e.db.execute('SELECT object_path FROM snapshots LIMIT 1').fetchone()[0]; (e.root/p).write_bytes(b'altered')
        with self.assertRaises(ValueError): stage.execute(self.source, self.output)
        self.assertFalse(self.output.exists())

    def test_missing_custody_is_not_recreated_by_verifier(self):
        with self.assertRaises(ValueError): stage.verify(self.output)
        self.assertFalse(self.output.exists())


if __name__ == '__main__': unittest.main()
