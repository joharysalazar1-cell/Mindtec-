import importlib.util
from pathlib import Path
import streamlit as st
from src.services.auto_sources import synchronize

st.set_page_config(page_title='MindTEC Intelligence System',page_icon='📊',layout='wide')
ROOT=Path(__file__).resolve().parent
PAGES={
    'Fuentes automáticas':('11_connections.py','render'),
    'Cargar bases de datos':('01_data_upload.py','pagina_recepcion_datos'),
    'Auditoría de la base':('10_audit_workspace.py','audit'),
    'Contraste de fuentes':('10_audit_workspace.py','contrast'),
    'Indicadores verificables':('10_audit_workspace.py','indicators'),
    'Auditoría avanzada':('09_indicator_audit.py',None),
    'Explorador de datos':('02_data_explorer.py','render'),
    'Modelo de datos':('03_data_model.py','render'),
    'Análisis descriptivo':('04_descriptive_analysis.py','render'),
    'Tablas cruzadas':('05_crosstabs.py','render'),
    'Exploración comercial':('06_market_intelligence.py','render'),
    'Modelos estadísticos':('07_statistical_models.py','render'),
    'Resultados y hallazgos':('10_audit_workspace.py','results'),
    'Inventario de fuentes':('08_results.py','render'),
}


@st.fragment(run_every=60)
def refresh_sources():
    try:
        config,changed=synchronize(st.session_state)
        if config:
            errors=sum(s.get('estado','').startswith('Error') for s in st.session_state.get('api_status',{}).values())
            st.caption(f'Fuentes API: {len(config)} · con error: {errors}. Detalle en Fuentes automáticas.')
            if changed:st.rerun()
    except Exception:
        st.warning('Configuración API inválida. Revisa Fuentes automáticas.')


def demo_sources():
    import hashlib
    if st.session_state.get('archivos_cargados'):return
    samples={
        'DEMO_sintetica_observaciones.csv': 'tienda,elegible,marca,caras_marca,caras_totales,precio_bs,frio,quiebre\nD01,1,Demo,4,10,10,1,0\nD02,1,Demo,6,10,12,1,0\nD03,1,Otra,0,10,11,0,1\nD04,1,Demo,3,10,13,0,1\nD05,0,Otra,0,0,9,0,0\n',
        'DEMO_sintetica_referencia.csv':'tienda,elegible,marca,caras_marca,caras_totales,precio_bs,frio,quiebre\nD01,1,Demo,4,10,10,1,0\nD02,1,Demo,5,10,12,1,0\nD03,1,Otra,0,10,11,0,1\nD06,1,Demo,2,10,14,0,1\n'}
    records=st.session_state.setdefault('archivos_cargados',{})
    for name,text in samples.items():
        content=text.encode('utf-8')
        records[hashlib.sha256(content).hexdigest()]=dict(nombre=name,contenido=content,extension='csv',tamano=len(content),hojas=None,origen='demo')


refresh_sources()
demo_sources()

def load_page(filename):
    path=ROOT/'interface'/'pages'/filename
    spec=importlib.util.spec_from_file_location('mindtec_'+filename.replace('.','_'),path)
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

st.sidebar.title('📊 MindTEC')
st.sidebar.caption('Demo sintética incluida para explorar sin cargar archivos. Las fuentes reales se identifican por su nombre y procedencia.')
choice=st.sidebar.radio('Navegación',['Inicio']+list(PAGES))
if choice=='Inicio':
    st.title('MindTEC · Auditoría y análisis independiente')
    st.caption('Fuentes → integridad → indicadores → contraste → hallazgos')
    st.info('Carga tus bases y referencias en Cargar bases de datos. Luego revisa su integridad, calcula indicadores con denominador explícito y contrasta fuentes equivalentes.')
    st.markdown('1. **Auditoría de la base:** claves, faltantes y duplicados.\n2. **Indicadores verificables:** presencia, caras o quiebres con base explícita.\n3. **Contraste de fuentes:** dashboard, facturas, declaraciones o referencias externas.\n4. **Resultados y hallazgos:** evidencia, interpretación y resolución del analista.')
    st.warning('Las fuentes originales no se modifican. Los resultados viven en la sesión: descarga el expediente para conservarlos. No confundas compra documentada con venta total o participación de mercado.')
else:
    filename,method=PAGES[choice]
    try:
        page=load_page(filename)
        if method is not None:
            getattr(page,method)()
    except Exception as exc:
        st.error(f'Error en el módulo «{choice}»: {exc}')
        st.exception(exc)
