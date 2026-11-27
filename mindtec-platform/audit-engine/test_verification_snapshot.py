"""Deterministic writer commit between verifier queries; no timing assumptions."""
import tempfile
import unittest
from pathlib import Path

from engine import Engine, canonical
from test_engine import POLICY, snapshot, visit


class QueryHook:
    def __init__(self, db, callback):
        self.db, self.callback = db, callback
        self.armed = True

    def execute(self, sql, *args):
        if sql == 'SELECT * FROM snapshots' and self.armed:
            self.armed = False
            self.callback()
        return self.db.execute(sql, *args)

    def __getattr__(self, name):
        return getattr(self.db, name)


class VerificationSnapshotTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.source = self.root / 'source.json'
        self.source.write_text(canonical(snapshot(visit())), encoding='utf-8')

    def test_writer_commit_between_queries_does_not_mix_snapshots(self):
        with Engine(self.root / 'runtime') as reader, Engine(self.root / 'runtime') as writer:
            old_head = reader.verify()
            reader.db = QueryHook(reader.db, lambda: writer.ingest(self.source, POLICY))
            self.assertEqual(reader.verify(), old_head)
            self.assertEqual(reader.db.execute('SELECT count(*) FROM runs').fetchone()[0], 1)
            self.assertNotEqual(reader.verify(), old_head)
            self.assertFalse(reader.db.in_transaction)

    def test_outer_transaction_remains_open(self):
        with Engine(self.root / 'runtime') as reader:
            reader.db.execute('BEGIN')
            reader.verify()
            self.assertTrue(reader.db.in_transaction)
            reader.db.execute('ROLLBACK')

    def test_corruption_rolls_back_only_verification_savepoint(self):
        with Engine(self.root / 'runtime') as reader:
            reader.ingest(self.source, POLICY)
            row = reader.db.execute('SELECT object_path FROM snapshots LIMIT 1').fetchone()
            path = reader.root / row[0]
            original = path.read_bytes()
            path.write_bytes(b'changed')
            reader.db.execute('BEGIN')
            with self.assertRaises(ValueError): reader.verify()
            self.assertTrue(reader.db.in_transaction)
            reader.db.execute('ROLLBACK')
            path.write_bytes(original)
            self.assertTrue(reader.verify())
            self.assertFalse(reader.db.in_transaction)


if __name__ == '__main__': unittest.main()
