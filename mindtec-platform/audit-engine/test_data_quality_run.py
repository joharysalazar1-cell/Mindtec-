import json
from pathlib import Path
import tempfile
import unittest
import engine
import invoice_adapter
import invoice_pipeline
import collection_watch
import data_quality_run as runner
from test_invoice_pipeline import fixture_book
from test_invoices import POLICY,SCOPE


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.book=self.root/'source.xlsx';fixture_book(self.book,53.33);cut=invoice_adapter.workbook_cut(self.book,SCOPE)
        self.source=self.root/'source.json';self.source.write_text(json.dumps(cut,indent=2),encoding='utf-8')
        self.policy=self.root/'policy.json';self.policy.write_text(engine.canonical(POLICY),encoding='utf-8')
        self.invoice=self.root/'invoice';self.output=self.root/'quality'

    def prepare(self,original=True):
        return invoice_pipeline.execute(self.source,self.policy,self.invoice,original_workbook=self.book if original else None)

    def test_verified_original_roundtrip_exact_source_hash_and_idempotence(self):
        source=self.prepare();first=runner.execute(self.invoice,self.output);second=runner.execute(self.invoice,self.output)
        self.assertEqual(first['run_id'],second['run_id']);self.assertTrue(runner.verify(self.output)['custody_verified'])
        with engine.Engine(self.output) as e:
            row=e.db.execute('SELECT * FROM runs').fetchone();result=json.loads(collection_watch.object_bytes(e,row['snapshot_hash']))
            self.assertEqual(result['source_cut_sha256'],engine.sha(self.source.read_bytes()));self.assertEqual(result['source_invoice_run_id'],source['run_id']);self.assertNotEqual(result['source_cut_sha256'],result['canonical_cut_sha256'])
            self.assertEqual(e.db.execute('SELECT count(*) FROM runs').fetchone()[0],1)

    def test_missing_or_unverified_original_creates_no_output(self):
        with self.assertRaises(ValueError):runner.execute(self.invoice,self.output)
        self.assertFalse(self.output.exists());self.prepare(original=False)
        with self.assertRaises(ValueError):runner.execute(self.invoice,self.output)
        self.assertFalse(self.output.exists())

    def test_overlapping_custody_is_rejected(self):
        for target in [self.invoice,self.invoice/'nested',self.root]:
            with self.assertRaises(ValueError):runner.execute(self.invoice,target)

    def test_catalogue_is_retained_as_valid_json_envelope(self):
        self.prepare();catalogue=self.root/'catalogue.csv';catalogue.write_text('Código en Kobo;Marca\nsku_1;A\n',encoding='utf-8');runner.execute(self.invoice,self.output,catalogue)
        with engine.Engine(self.output) as e:
            refs=json.loads(e.db.execute('SELECT rules_json FROM runs').fetchone()[0])['reference_sources'];envelope=json.loads(collection_watch.object_bytes(e,refs['dated_catalogue']));self.assertEqual(envelope['original_sha256'],engine.sha(catalogue.read_bytes()))
        self.assertTrue(runner.verify(self.output)['custody_verified'])

    def test_consistent_but_fabricated_output_fails_replay(self):
        self.prepare();runner.execute(self.invoice,self.output)
        with engine.Engine(self.output) as e:
            row=e.db.execute('SELECT * FROM runs').fetchone();rules=json.loads(row['rules_json']);result=json.loads(collection_watch.object_bytes(e,row['snapshot_hash']));result['periods'][0]['lines']=999
            refs={name:(collection_watch.object_bytes(e,hash_),'.xlsx' if name=='original_workbook' else '.json')for name,hash_ in rules['reference_sources'].items()}
            forged=e.record_result(engine.canonical(result).encode(),json.loads(row['policy_json']),rules,result['findings'],references=refs)
        with self.assertRaisesRegex(ValueError,'replay'):runner.verify(self.output,forged['run_id'])


if __name__=='__main__':unittest.main()
