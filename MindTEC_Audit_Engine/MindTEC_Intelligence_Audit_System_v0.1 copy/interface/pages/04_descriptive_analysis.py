import streamlit as st
import pandas as pd
import plotly.express as px
from src.services.workspace import select_data,csv_button

def render():
    st.title('📐 Análisis descriptivo')
    df,_=select_data(key='desc')
    if df is None:return
    col=st.selectbox('Variable',list(df.columns),key='desc_col')
    s=df[col]; st.write('Valores válidos:',int(s.notna().sum()),' · Faltantes:',int(s.isna().sum()))
    if pd.api.types.is_numeric_dtype(s):
        desc=s.describe().rename_axis('estadístico').reset_index(name='valor')
        st.dataframe(desc,use_container_width=True,hide_index=True)
        st.plotly_chart(px.histogram(df,x=col,title='Distribución'),use_container_width=True)
        csv_button(desc,'estadisticos.csv')
    else:
        counts=s.fillna('(sin dato)').astype(str).value_counts(dropna=False).rename_axis('categoria').reset_index(name='frecuencia')
        counts['porcentaje']=counts['frecuencia']/len(s)*100
        st.dataframe(counts,use_container_width=True,hide_index=True)
        st.plotly_chart(px.bar(counts.head(30),x='categoria',y='frecuencia',title='Frecuencias (hasta 30 categorías)'),use_container_width=True)
        csv_button(counts,'frecuencias.csv')
