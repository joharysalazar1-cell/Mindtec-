import copy
import unittest
import cold_legacy_reference as cold


def fixture(rows=None, expected=2, selected='a b', gate='si'):
    answers = {}; cells = {}; ids = []
    def add(route, value):
        cell = {'source_sha256': 'source', 'sheet': 'Envíos', 'coordinate': 'A'+str(len(cells)+2), 'source_row': len(cells)+2, 'column': route, 'kobo_id': '1', 'value': value}
        cid = cold.digest(cell); cells[cid] = cell
        a = {'route': route, 'state': 'empty_observation' if value is None else 'observed', 'value': value, 'cell_ids': [cid]}
        aid = cold.digest(a); answers[aid] = a; ids.append(aid)
    add('g/hay_enfriadores', gate); add('g/n_marcas_frias', expected); add('g/marcas_frias_seleccionadas', selected)
    for i, (code, count) in enumerate(rows if rows is not None else [('a', 10), ('b', 30)], 1):
        add('rep_caras_frias['+str(i)+']/marca_fria_actual', code)
        add('rep_caras_frias['+str(i)+']/caras_frias', count)
    inv = {'month': '2026-09', 'kobo_id': '1', 'layout': 'legacy_global_unattributed', 'state': 'pending', 'answer_ids': ids}
    return {'source_sha256': 'source', 'category_inventories': [inv, copy.deepcopy(inv)], 'answer_evidence': answers, 'cells': cells}


class Tests(unittest.TestCase):
    def run_reference(self, source):
        return cold.reconstruct(source, [{'brand_code': 'a', 'brand': 'A'}, {'brand_code': 'c', 'brand': 'C'}])

    def test_unique_visits_never_duplicate_global_denominator_across_categories(self):
        r = self.run_reference(fixture()); self.assertEqual(len(r['stores']), 1)
        a = next(x for x in r['monthly'] if x['brand_code'] == 'a')
        self.assertEqual((a['numerator_in_complete_visits'], a['denominator_in_complete_visits'], a['whole_cohort_share']), (10, 40, 25))
        self.assertEqual(next(x for x in r['monthly'] if x['brand_code'] == 'c')['whole_cohort_share'], 0)
        self.assertTrue(any(x['brand_code'] == 'b' for x in r['monthly']))

    def test_incomplete_or_invalid_enumerations_never_become_complete(self):
        for source in [fixture(expected=3), fixture(selected='a'), fixture(selected='a a'), fixture(rows=[('a', 10), ('a', 30)]), fixture(rows=[('a', 10), ('b', None)]), fixture(rows=[('a', -1), ('b', 30)]), fixture(rows=[('a', True), ('b', 30)])]:
            self.assertEqual(self.run_reference(source)['stores'][0]['state'], 'pending')

    def test_confirmed_no_cooler_allows_empty_exported_repeat_slots(self):
        s = fixture(rows=[(None, None)], expected=None, selected=None, gate='no')
        s['category_inventories'].append(dict(s['category_inventories'][0], layout='explicit_no_coolers', state='complete'))
        r = self.run_reference(s); self.assertEqual(r['stores'][0]['recorded_faces'], 0)
        self.assertEqual(r['monthly'][0]['state'], 'zero_recorded_faces')

    def test_negative_gate_with_filled_row_remains_pending(self):
        s = fixture(gate='no'); s['category_inventories'].append(dict(s['category_inventories'][0], layout='explicit_no_coolers', state='complete'))
        self.assertEqual(self.run_reference(s)['stores'][0]['state'], 'pending')

    def test_original_cells_and_answers_are_verified_and_not_mutated(self):
        s = fixture(); before = copy.deepcopy(s); self.run_reference(s); self.assertEqual(s, before)
        next(iter(s['cells'].values()))['value'] = 'tampered'
        with self.assertRaises(ValueError): self.run_reference(s)


if __name__ == '__main__':
    unittest.main()
