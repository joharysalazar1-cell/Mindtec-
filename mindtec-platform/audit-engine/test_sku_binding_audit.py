import unittest
from sku_binding_audit import audit, label_brand


class BindingAuditTests(unittest.TestCase):
    def fixture(self):
        headers = ['ID envío', 'Mes', 'Marca', 'SKUs (códigos Kobo)', 'SKUs (maestro)']
        rows = [dict(source_row=2, cells=[1, '2026-09', 'Red Bull', 'sku_1 sku_2', 'Tampico Citrus 3 L'],
                     coordinates=['A2', 'B2', 'C2', 'D2', 'E2']),
                dict(source_row=3, cells=[2, '2026-10', 'Tampico', 'sku_7', 'Tampico Citrus 3 L'],
                     coordinates=['A3', 'B3', 'C3', 'D3', 'E3'])]
        cut = {'tables': [{'sheet': 'Colecta · marcas', 'headers': headers, 'rows': rows}],
               'provenance': {'original_sha256': 'test-source'}}
        config = {'schema': 'mindtec-observed-client-core-configuration/1',
                  'clients': [{'id': 'client', 'core_skus': ['Tampico Citrus 3 L', 'Unknown 2 L']}]}
        return cut, config

    def test_cross_brand_preserves_originals_without_pairing(self):
        cut, config = self.fixture()
        result = audit(cut, config)
        finding = result['findings'][0]
        self.assertEqual(result['summary']['rows_with_signals'], 1)
        self.assertEqual(len(finding['signals']), 2)
        self.assertEqual(finding['coordinates']['SKUs (maestro)'], 'E2')
        self.assertEqual(finding['values']['Marca'], 'Red Bull')
        self.assertEqual(finding['codes'], ['sku_1', 'sku_2'])
        self.assertFalse(finding['positional_pairing_performed'])
        self.assertEqual(finding['review_status'], 'pending')

    def test_literal_occurrence_is_not_historical_applicability(self):
        result = audit(*self.fixture())
        client = result['clients'][0]
        self.assertEqual(client['historical_applicability'], 'not_established')
        self.assertTrue(client['skus'][0]['literal_name_seen_in_export'])
        self.assertFalse(client['skus'][1]['literal_name_seen_in_export'])

    def test_longest_boundary_and_unknown(self):
        self.assertEqual(label_brand('Del Valle 2 L', ['Del', 'Del Valle']), 'Del Valle')
        self.assertIsNone(label_brand('Pilar 2 L', ['Pil']))
        self.assertIsNone(label_brand('Unmapped 2 L', ['Pil']))

    def test_formula_rejected(self):
        cut, config = self.fixture()
        cut['tables'][0]['formula_cells_using_cached_values'] = 1
        with self.assertRaises(ValueError):
            audit(cut, config)

    def test_duplicate_clients_rejected(self):
        cut, config = self.fixture()
        config['clients'] *= 2
        with self.assertRaises(ValueError):
            audit(cut, config)


if __name__ == '__main__':
    unittest.main()
