import streamlit as st
import pandas as pd
from src.services.workspace import select_data, csv_button

def render():
    st.title('🔎 Explorador de datos')
    df, _ = select_data(key='explore')
    if df is None: return
    a,b,c = st.columns(3)
    a.metric('Registros',len(df)); b.metric('Variables',len(df.columns)); c.metric('Celdas vacías',int(df.isna().sum().sum()))
    selected = st.multiselect('Columnas visibles', list(df.columns), default=list(df.columns))
    if not selected: return
    filtered = df[selected].copy()
    filter_col = st.selectbox('Filtrar por variable (opcional)', ['(sin filtro)']+selected)
    if filter_col != '(sin filtro)':
        vals = filtered[filter_col].dropna().astype(str).unique().tolist()
        if len(vals) <= 1000:
            chosen = st.multiselect('Valores permitidos', sorted(vals), default=[])
            if chosen: filtered = filtered[filtered[filter_col].astype(str).isin(chosen)]
        else:
            st.warning('Demasiados valores únicos para el selector; el filtro se omite.')
    st.dataframe(filtered.head(1000), use_container_width=True)
    st.caption('Vista limitada a 1.000 filas; la exportación incluye todas las filas filtradas.')
    profile = pd.DataFrame({'variable':df.columns,'tipo':df.dtypes.astype(str).values,'no_nulos':df.notna().sum().values,'nulos':df.isna().sum().values,'unicos':df.nunique(dropna=True).values})
    st.subheader('Perfil de variables'); st.dataframe(profile, use_container_width=True, hide_index=True)
    csv_button(filtered, 'exploracion.csv')
