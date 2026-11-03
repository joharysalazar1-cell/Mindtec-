import unittest
import pandas as pd
from src.audit_core import reconcile, ratio_metric, quality_report


class AuditTests(unittest.TestCase):
    def test_outer_comparison_zero_and_missing(self):
        a=pd.DataFrame({'id':['a','b','c'],'v':[1,5,2]})
        b=pd.DataFrame({'key':['a','b','d'],'val':[1,0,3]})
        original=a.copy(deep=True)
        r=reconcile(a,b,['id'],['key'],'v','val').set_index('clave_1')
        self.assertEqual(r.loc['a','estado'],'Coincidencia exacta')
        self.assertTrue(pd.isna(r.loc['b','diferencia_pct']))
        self.assertEqual(r.loc['c','estado'],'Solo en base')
        self.assertEqual(r.loc['d','estado'],'Solo en referencia')
        pd.testing.assert_frame_equal(a,original)

    def test_rejects_many_to_many_and_incomplete_keys(self):
        for ids in (['a','a'],['a',None]):
            a=pd.DataFrame({'id':ids,'v':[1,2]})
            with self.assertRaises(ValueError):reconcile(a,a,['id'],['id'],'v','v')

    def test_tolerance_and_invalid_numeric(self):
        a=pd.DataFrame({'id':['a'],'v':[101]})
        b=pd.DataFrame({'id':['a'],'v':[100]})
        self.assertEqual(reconcile(a,b,['id'],['id'],'v','v',rtol=.02).iloc[0]['estado'],'Dentro de tolerancia')
        a['v']='no es un número'
        with self.assertRaises(ValueError):reconcile(a,b,['id'],['id'],'v','v')

    def test_distinct_eligible_stores(self):
        d=pd.DataFrame({'tienda':['a','a','b','c'],'vende':[1,1,1,0],'marca':['Pil','Pil','Otra','Pil']})
        self.assertEqual(ratio_metric(d,'Tiendas','marca','Pil','tienda','vende','1'),(1,2,50))

    def test_ratio_of_sums_and_bad_denominator(self):
        d=pd.DataFrame({'marca':[72,0],'total':[98,2]})
        self.assertEqual(ratio_metric(d,'Caras','marca','total'),(72,100,72))
        with self.assertRaises(ValueError):ratio_metric(pd.DataFrame({'a':[2],'b':[1]}),'Caras','a','b')
        with self.assertRaises(ValueError):ratio_metric(pd.DataFrame({'a':[0],'b':[0]}),'Caras','a','b')

    def test_quality_records_all_duplicate_keys(self):
        r=quality_report(pd.DataFrame({'id':[1,1,None]}),['id']).set_index('control')
        self.assertEqual(r.loc['Clave repetida','casos'],2)
        self.assertEqual(r.loc['Clave incompleta','casos'],1)


if __name__=='__main__':unittest.main()
