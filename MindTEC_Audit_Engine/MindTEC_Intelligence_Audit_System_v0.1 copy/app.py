import importlib.util
from pathlib import Path
import streamlit as st

st.set_page_config(page_title='MindTEC Intelligence System',page_icon='📊',layout='wide')
ROOT=Path(__file__).resolve().parent
PAGES={
    'Recepción de datos':('01_data_upload.py','pagina_recepcion_datos'),
    'Explorador de datos':('02_data_explorer.py','render'),
    'Modelo de datos':('03_data_model.py','render'),
    'Análisis descriptivo':('04_descriptive_analysis.py','render'),
    'Tablas cruzadas':('05_crosstabs.py','render'),
    'Inteligencia comercial':('06_market_intelligence.py','render'),
    'Modelos estadísticos':('07_statistical_models.py','render'),
    'Resultados':('08_results.py','render'),
}

def load_page(filename):
    path=ROOT/'interface'/'pages'/filename
    spec=importlib.util.spec_from_file_location('mindtec_'+filename.replace('.','_'),path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

st.sidebar.title('📊 MindTEC')
choice=st.sidebar.radio('Navegación',['Inicio']+list(PAGES))
if choice=='Inicio':
    st.title('MindTEC Intelligence System')
    st.caption('Plataforma de investigación de mercados e inteligencia comercial · versión funcional inicial')
    st.info('Comienza en Recepción de datos. Las fuentes se conservan en memoria durante la sesión y no se modifican.')
    st.write('Módulos disponibles:',len(PAGES))
    st.warning('La validez de cada análisis depende de la unidad de observación, calidad, cobertura y diseño muestral. Las 12 aristas requieren fuentes apropiadas.')
else:
    filename,method=PAGES[choice]
    try:
        getattr(load_page(filename),method)()
    except Exception as exc:
        st.error(f'Error en el módulo «{choice}»: {exc}')
        st.exception(exc)
