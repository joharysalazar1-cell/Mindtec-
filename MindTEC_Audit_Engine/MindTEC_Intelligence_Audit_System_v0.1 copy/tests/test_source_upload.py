import tempfile
import unittest
from pathlib import Path
import pandas as pd
from streamlit.testing.v1 import AppTest
from src.source_checks import check_source, register_upload
from src.services.source_history import save_snapshot, restore_snapshot, list_snapshots


class UploadTests(unittest.TestCase):
    def test_same_name_different_content_retains_both_versions(self):
        state={}
        a=register_upload(state,'base.csv',b'id,valor\n1,2\n')
        b=register_upload(state,'base.csv',b'id,valor\n1,3\n')
        self.assertNotEqual(a,b)
        self.assertEqual(len(state['archivos_cargados']),2)
        self.assertEqual(register_upload(state,'base.csv',b'id,valor\n1,2\n'),a)

    def test_history_roundtrip_integrity_and_period(self):
        state={}
        digest=register_upload(state,'base.csv',b'id,valor\n001,2\n')
        with tempfile.TemporaryDirectory() as directory:
            name=save_snapshot(state['archivos_cargados'][digest],{'periodo':'octubre 2026'},directory)
            self.assertEqual(len(list_snapshots(directory)),1)
            recovered={}
            restore_snapshot(name,recovered,directory)
            self.assertEqual(recovered['archivos_cargados'][digest]['contenido'],b'id,valor\n001,2\n')
            self.assertEqual(recovered['source_metadata'][digest]['periodo'],'octubre 2026')
            (Path(directory)/(digest+'.bin')).write_bytes(b'alterado')
            with self.assertRaises(ValueError):restore_snapshot(name,{},directory)

    def test_invoice_profile_does_not_certify_census(self):
        df=pd.DataFrame(columns=['ID factura','Código sticker','Total factura','Fecha de emisión'])
        self.assertTrue(check_source(df,'Facturas').estado.eq('Detectado').all())
        self.assertFalse(check_source(df,'Censo / observaciones de campo').estado.eq('Detectado').all())

    def test_upload_page_with_same_name_versions(self):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=40).run()
        state={}
        register_upload(state,'base.csv',b'id,valor\n1,2\n')
        register_upload(state,'base.csv',b'id,valor\n1,3\n')
        app.session_state['archivos_cargados']=state['archivos_cargados']
        app.sidebar.radio[0].set_value('Cargar bases de datos').run()
        self.assertEqual(len(app.exception),0)
        self.assertIn('Cargar y verificar bases de datos',app.title[0].value)
        selector=next(s for s in app.selectbox if s.label=='Selecciona un archivo para explorar')
        self.assertEqual(len(selector.options),2)


if __name__=='__main__':unittest.main()
