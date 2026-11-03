import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
from scipy import stats
from src.services.workspace import select_data,csv_button

def render():
    st.title('📊 Modelos estadísticos')
    df,_=select_data(key='stats')
    if df is None:return
    nums=list(df.select_dtypes(include='number').columns)
    test=st.selectbox('Procedimiento',['Correlación Pearson/Spearman','Regresión lineal exploratoria'])
    if len(nums)<2:st.info('Se necesitan al menos dos variables numéricas.');return
    x=st.selectbox('Variable explicativa X',nums,key='stat_x')
    y=st.selectbox('Variable respuesta Y',nums,index=1,key='stat_y')
    if x==y:st.warning('Selecciona variables diferentes.');return
    dat=df[[x,y]].replace([np.inf,-np.inf],np.nan).dropna()
    if len(dat)<3:st.warning('Menos de tres pares válidos.');return
    if dat[x].nunique()<2 or dat[y].nunique()<2:st.warning('Se requiere variación en ambas variables.');return
    if test.startswith('Correlación'):
        pearson=stats.pearsonr(dat[x],dat[y]); spearman=stats.spearmanr(dat[x],dat[y])
        st.write(f'Pearson r = {pearson.statistic:.4f} · p = {pearson.pvalue:.5g}')
        st.write(f'Spearman ρ = {spearman.statistic:.4f} · p = {spearman.pvalue:.5g}')
    else:
        import statsmodels.api as sm
        model=sm.OLS(dat[y],sm.add_constant(dat[x])).fit()
        st.write(f'Coeficiente X = {model.params.iloc[1]:.5g} · p = {model.pvalues.iloc[1]:.5g} · R² = {model.rsquared:.4f}')
        with st.expander('Resumen del modelo'):
            st.text(model.summary().as_text())
        st.warning('Regresión exploratoria sin ajuste por confusores ni diagnóstico completo de supuestos. No es un pronóstico validado ni prueba causal.')
    st.plotly_chart(px.scatter(dat,x=x,y=y,title=f'{x} frente a {y}'),use_container_width=True)
    st.caption(f'N pares completos = {len(dat)}. Verifica independencia, muestreo y supuestos antes de interpretar valores p.')
