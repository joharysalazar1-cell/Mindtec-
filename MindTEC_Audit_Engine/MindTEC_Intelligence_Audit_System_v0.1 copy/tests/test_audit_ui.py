import unittest
from pathlib import Path
from streamlit.testing.v1 import AppTest


class AuditInterfaceTests(unittest.TestCase):
    def test_contrast_saves_evidence_and_rejects_unconfirmed_scope(self):
        app=AppTest.from_file(str(Path(__file__).resolve().parents[1]/'app.py'),default_timeout=40).run()
        app.session_state['archivos_cargados']={
            'basehash':dict(nombre='base.csv',extension='csv',contenido=b'id,value\na,10\nb,20\n',tamano=24),
            'refhash':dict(nombre='referencia.csv',extension='csv',contenido=b'id,value\na,10\nb,18\n',tamano=24)}
        app.sidebar.radio[0].set_value('Contraste de fuentes').run()
        app.selectbox(key='compare_right').set_value('refhash').run()
        app.multiselect(key='cmp_lk').set_value(['id'])
        app.multiselect(key='cmp_rk').set_value(['id'])
        app.selectbox(key='cmp_lv').set_value('value')
        app.selectbox(key='cmp_rv').set_value('value')
        app.text_input(key='cmp_l_period').set_value('octubre 2026')
        app.text_input(key='cmp_r_period').set_value('octubre 2026')
        app.text_area[0].set_value('Mismo universo, suma documentada en Bs por id')
        app.button[0].click().run()
        self.assertEqual(len(app.warning),1)
        app.checkbox[0].check()
        app.button[0].click().run()
        self.assertEqual(len(app.exception),0)
        results=app.session_state['audit_results']
        table=next(iter(results.values()))['tabla']
        self.assertEqual(table['estado'].tolist(),['Coincidencia exacta','Diferencia no explicada'])
        app.sidebar.radio[0].set_value('Resultados y hallazgos').run()
        self.assertEqual(len(app.exception),0)
        self.assertEqual(len(app.dataframe),1)


if __name__=='__main__':unittest.main()
