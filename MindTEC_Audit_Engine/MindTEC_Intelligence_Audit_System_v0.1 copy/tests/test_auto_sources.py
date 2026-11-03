import json
import unittest
from unittest.mock import patch
from src.services.auto_sources import decode_table, synchronize


class AutoSourcesTests(unittest.TestCase):
    def test_nested_records_and_reject_wrong_shape(self):
        frame=decode_table(json.dumps({'data':{'items':[{'tienda':'001','precio':12}]}}).encode(),'json','data.items')
        self.assertEqual(frame.iloc[0]['tienda'],'001')
        with self.assertRaises(ValueError):decode_table(b'{"data":5}','json','data')

    def test_csv_preserves_identifiers(self):
        frame=decode_table(b'tienda,valor\n001,2\n','csv')
        self.assertEqual(frame.iloc[0]['tienda'],'001')

    @patch('src.services.auto_sources.configured_sources',return_value=[{'id':'a','name':'Fuente','refresh_seconds':300}])
    def test_refresh_interval_and_failed_refresh_keep_snapshot(self,_):
        state={}
        def fetch(_):return 'hash',dict(filas=2,actualizado_utc='2026-11-03',contenido=b'csv')
        _,changed=synchronize(state,fetcher=fetch)
        self.assertTrue(changed)
        _,changed=synchronize(state,fetcher=lambda _:self.fail('No debe consultar antes del intervalo'))
        self.assertFalse(changed)
        def failed(_):raise RuntimeError('secret must never appear')
        synchronize(state,force=True,fetcher=failed)
        self.assertIn('hash',state['archivos_cargados'])
        self.assertNotIn('secret',str(state['api_status']))


if __name__=='__main__':unittest.main()
