import streamlit as st
import pandas as pd
from src.services.workspace import sources,get_df,csv_button

def render():
    st.title('📦 Resultados y exportaciones')
    st.caption('Los resultados se exportan desde cada módulo; aquí se muestra el inventario de fuentes de la sesión.')
    data=sources()
    if not data:st.info('Todavía no hay fuentes cargadas.');return
    rows=[]
    for k,r in data.items():
        try:
            df=get_df(k)
            rows.append({'fuente':r['nombre'],'id_sha256':k,'registros':len(df),'variables':len(df.columns),'tamano_bytes':r['tamano']})
        except Exception as e:rows.append({'fuente':r['nombre'],'error':str(e)})
    result=pd.DataFrame(rows)
    st.dataframe(result,use_container_width=True,hide_index=True)
    csv_button(result,'inventario_fuentes.csv')
    st.warning('No se han generado informes automáticos ni se han alterado las fuentes originales.')
