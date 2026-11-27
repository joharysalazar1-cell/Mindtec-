import copy
import unittest
from historical_sku_contrast import compare
from kobo_label_evidence import extract
import test_kobo_label_evidence


class HistoricalSkuTests(unittest.TestCase):
    def fixture(self):
        labels=extract(test_kobo_label_evidence.workbook())
        headers=['ID envío','Mes','Marca','Marca (código)','Subcategoría (código)',
                 'SKUs (códigos Kobo)','SKUs (maestro)']
        cut={'provenance':{'original_sha256':'normalized'},'tables':[{'sheet':'Colecta · marcas',
             'headers':headers,'rows':[{'source_row':2,'cells':[7,'2026-09','Red Bull','red_bull',
             'bsa_energy','sku_1','Tampico 3 L'],'coordinates':['A2','B2','C2','D2','E2','F2','G2']}]}]}
        return labels,cut,{'rows':[{'internal_id':7,'kobo_id':'123'}]}

    def test_exact_versioned_row_recovered_without_correction(self):
        result=compare(*self.fixture())
        row=result['rows'][0]
        self.assertEqual(row['state'],'unique_historical_row_recovered')
        self.assertFalse(row['literal_label_sets_equal'])
        self.assertFalse(row['automatic_correction'])
        self.assertFalse(row['historical_code_mapping_certified'])
        self.assertEqual(row['selected_label_cells'][0]['label'],'Red Bull 250 ml')

    def test_duplicate_candidate_not_silently_selected(self):
        labels,cut,walk=self.fixture();labels['tables'][1]['records']*=2
        self.assertEqual(compare(labels,cut,walk)['rows'][0]['state'],'ambiguous_historical_rows')

    def test_missing_id_never_matches_by_row_order(self):
        labels,cut,walk=self.fixture();walk['rows'][0]['kobo_id']='other'
        self.assertEqual(compare(labels,cut,walk)['rows'][0]['state'],'no_historical_row')

    def test_parent_conflict_not_recovered(self):
        labels,cut,walk=self.fixture();labels['tables'][1]['records'][0]['parent_binding_state']='unresolved'
        self.assertEqual(compare(labels,cut,walk)['rows'][0]['state'],'historical_parent_unresolved')

    def test_duplicate_identity_crosswalk_rejected(self):
        labels,cut,walk=self.fixture();walk['rows']*=2
        with self.assertRaises(ValueError):compare(labels,cut,walk)


if __name__=='__main__':unittest.main()
