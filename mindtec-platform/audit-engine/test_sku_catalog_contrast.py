import unittest
from sku_catalog_contrast import contrast
import test_sku_binding_audit


class CatalogContrastTests(unittest.TestCase):
    def test_dated_conflict_never_certifies_or_corrects(self):
        cut, _ = test_sku_binding_audit.BindingAuditTests().fixture()
        raw = 'Código en Kobo;Marca;Valor del catálogo\nsku_1;Tampico;Tampico 3 L\nsku_7;Tampico;Tampico 3 L\n'.encode()
        result = contrast(cut, raw)
        self.assertEqual(result['summary']['code_occurrences'], 3)
        self.assertEqual([r['status'] for r in result['rows']],
                         ['brand_differs_from_dated_catalog', 'code_not_in_dated_catalog',
                          'brand_matches_dated_catalog'])
        self.assertTrue(all(not r['historical_mapping_certified'] and not r['automatic_correction']
                            for r in result['rows']))

    def test_duplicate_codes_are_ambiguous_even_with_identical_labels(self):
        cut, _ = test_sku_binding_audit.BindingAuditTests().fixture()
        raw = ('Código en Kobo;Marca;Valor del catálogo\n' + 'sku_1;Tampico;Tampico 3 L\n' * 2).encode()
        self.assertEqual(contrast(cut, raw)['rows'][0]['status'], 'ambiguous_catalog_code')

    def test_missing_headers_rejected(self):
        with self.assertRaises(ValueError):
            contrast({}, b'code;brand\n')

    def test_missing_brand_is_not_a_match(self):
        cut, _ = test_sku_binding_audit.BindingAuditTests().fixture()
        cut['tables'][0]['rows'][0]['cells'][2] = ''
        raw = 'Código en Kobo;Marca;Valor del catálogo\nsku_1;;Some SKU\n'.encode()
        self.assertEqual(contrast(cut, raw)['rows'][0]['status'], 'missing_brand_evidence')

    def test_invalid_month_rejected(self):
        cut, _ = test_sku_binding_audit.BindingAuditTests().fixture()
        cut['tables'][0]['rows'][0]['cells'][1] = '2026-13'
        raw = 'Código en Kobo;Marca;Valor del catálogo\n'.encode()
        with self.assertRaises(ValueError):
            contrast(cut, raw)

    def test_malformed_csv_rejected(self):
        cut, _ = test_sku_binding_audit.BindingAuditTests().fixture()
        with self.assertRaises(ValueError):
            contrast(cut, 'Código en Kobo;Marca;Valor del catálogo\nsku_1;Pil\n'.encode())

    def test_monthly_counts_reconcile(self):
        cut, _ = test_sku_binding_audit.BindingAuditTests().fixture()
        raw = 'Código en Kobo;Marca;Valor del catálogo\n'.encode()
        monthly = contrast(cut, raw)['summary']['monthly_status_counts']
        self.assertEqual(monthly, {'2026-09': {'code_not_in_dated_catalog': 2},
                                   '2026-10': {'code_not_in_dated_catalog': 1}})


if __name__ == '__main__':
    unittest.main()
