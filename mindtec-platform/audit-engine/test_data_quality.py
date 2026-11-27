import copy
import json
import unittest
import data_quality as quality


def fixture(rows=None):
    headers = ['ID factura','Línea','Mes','Sticker','Total neto','ID SKU','Fecha de emisión','Precio unitario','Cantidad','Código Kobo SKU']
    records = rows or [['doc1',1,'2026-09','001',10,1,'2026-09-01',10,1,'sku_1'],['doc2',1,'2026-10','002',0,None,None,None,0,None]]
    return {'schema':'mindtec-invoice-cut/1','headers':headers,'rows':[{'source_row':i+2,'cells':row}for i,row in enumerate(records)],'scope':{'namespace':'test','currency':'BOB','period_basis':'collection_month','cohort_id':'synthetic','periods':['2026-09','2026-10']},'provenance':{'original_sha256':'synthetic','worksheet':'Ítems de facturas','date_system':'excel_1900'}}


class Tests(unittest.TestCase):
    def total(self, result): return next(p for p in result['periods'] if p['period']=='TOTAL')

    def test_overlapping_nulls_count_unique_rows_and_absent_cost_stays_unavailable(self):
        r = quality.evaluate(fixture()); t = self.total(r)
        self.assertEqual(t['completeness']['rows_with_any_available_critical_null']['numerator'], 1)
        self.assertEqual(t['completeness']['fields']['Costo unitario']['state'],'field_absent')
        self.assertIsNone(t['completeness']['fields']['Costo unitario']['percentage'])
        self.assertEqual(len([f for f in r['findings']if f['rule']=='critical_value_missing']),1)

    def test_duplicate_excess_involved_and_missing_keys_are_distinct(self):
        cut=fixture(); row=cut['rows'][0]['cells']; cut['rows'] += [{'source_row':4,'cells':copy.deepcopy(row)},{'source_row':5,'cells':[None,*row[1:]]}]
        r=quality.evaluate(cut); u=self.total(r)['uniqueness']
        self.assertEqual(u['duplicate_excess_rows']['numerator'],1); self.assertEqual(u['duplicate_involved_rows']['numerator'],2); self.assertEqual(u['missing_key']['numerator'],1)

    def test_real_zero_missing_and_invalid_numbers_are_distinct(self):
        cut=fixture(); cut['rows'][0]['cells'][7]=False
        t=self.total(quality.evaluate(cut))
        self.assertEqual(t['numeric_formats']['Precio unitario']['missing'],1)
        self.assertEqual(t['numeric_formats']['Precio unitario']['invalid_format']['numerator'],1)
        self.assertEqual(t['numeric_formats']['Cantidad']['zero']['numerator'],1)

    def test_referential_coverage_excludes_missing_and_marks_ambiguous_codes(self):
        master='Código en Kobo;Marca\nsku_1;A\nsku_1;B\n'.encode()
        t=self.total(quality.evaluate(fixture(),master))['referential_code_existence']
        self.assertEqual(t['code_presence']['percentage'],50)
        self.assertEqual(t['ambiguous_in_catalogue']['numerator'],1)
        self.assertEqual(t['absent_in_catalogue']['numerator'],0)
        self.assertTrue(t['not_full_sku_or_store_id_integrity'])

    def test_codes_are_not_coerced_or_zero_padded(self):
        cut=fixture(); cut['rows'][0]['cells'][-1]=12
        t=self.total(quality.evaluate(cut,'Código en Kobo;Marca\n0012;A\n'.encode()))['referential_code_existence']
        self.assertEqual(t['invalid_code_type'],1); self.assertIsNone(t['absent_in_catalogue']['percentage'])

    def test_invalid_dates_are_evaluated_only_with_supported_system(self):
        cut=fixture(); cut['rows'][0]['cells'][6]='not-a-date'
        self.assertEqual(self.total(quality.evaluate(cut))['document_dates']['numerator'],1)
        cut['provenance']['date_system']='unverified'
        self.assertEqual(self.total(quality.evaluate(cut))['document_dates']['state'],'date_system_or_field_not_supported')

    def test_empty_month_denominator_is_not_reported_as_zero_percent(self):
        cut=fixture(); cut['scope']['periods'].append('2026-11'); r=quality.evaluate(cut)
        empty=next(p for p in r['periods']if p['period']=='2026-11')
        self.assertIsNone(empty['completeness']['fields']['ID SKU']['percentage'])

    def test_original_input_preserved_and_findings_trace_to_source_rows(self):
        cut=fixture(); original=copy.deepcopy(cut); r=quality.evaluate(cut); self.assertEqual(cut,original)
        f=next(f for f in r['findings']if f['rule']=='critical_value_missing')
        self.assertEqual(f['evidence']['source_rows'],[3]); self.assertEqual(f['evidence']['line_keys'],['doc2|1']); self.assertEqual(f['evidence']['original_values'][0]['ID SKU'],None)
        self.assertEqual(r,quality.evaluate(cut))

    def test_original_byte_hash_is_distinct_from_canonical_hash(self):
        cut=fixture(); raw=json.dumps(cut,indent=2).encode(); result=quality.evaluate(cut,source_raw=raw)
        self.assertEqual(result['source_cut_sha256'],quality.sha(raw))
        self.assertNotEqual(result['source_cut_sha256'],result['canonical_cut_sha256'])
        self.assertIsNone(quality.evaluate(cut)['source_cut_sha256'])
        with self.assertRaises(ValueError):quality.evaluate(cut,source_raw=b'{}')

    def test_missing_code_column_is_not_mislabeled_as_missing_master(self):
        cut=fixture();cut['headers'].pop()
        for row in cut['rows']:row['cells'].pop()
        result=quality.evaluate(cut,'Código en Kobo;Marca\nsku_1;A\n'.encode())
        self.assertEqual(self.total(result)['referential_code_existence']['state'],'code_field_absent')


if __name__=='__main__': unittest.main()
