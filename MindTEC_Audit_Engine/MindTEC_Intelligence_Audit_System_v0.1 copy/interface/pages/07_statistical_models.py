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
    test=st.selectbox('Procedimiento',['Correlación Pearson/Spearman','Regresión lineal exploratoria','Regresión multivariable'])
    if len(nums)<2:st.info('Se necesitan al menos dos variables numéricas.');return
    if test=='Regresión multivariable':
        import statsmodels.api as sm
        y=st.selectbox('Variable respuesta',nums,key='multi_y')
        xs=st.multiselect('Variables explicativas',[c for c in nums if c!=y])
        kind=st.radio('Modelo',['Lineal OLS','Logístico binario'],horizontal=True)
        if not xs:st.info('Selecciona las variables explicativas según tu hipótesis.');return
        terms=st.multiselect('Interacción: selecciona exactamente dos explicativas',xs)
        if len(terms) not in (0,2):st.warning('La interacción requiere exactamente dos variables.');return
        dat=df[[y]+xs].replace([np.inf,-np.inf],np.nan).dropna()
        st.caption(f'{len(dat)} observaciones completas de {len(df)}; {len(df)-len(dat)} omitidas solo de este ajuste. Las fuentes permanecen intactas.')
        xmat=dat[xs].astype(float).copy()
        if terms:xmat['interaccion']=xmat[terms[0]]*xmat[terms[1]]
        xmat=sm.add_constant(xmat,has_constant='add')
        if len(dat)<=xmat.shape[1]+2:st.warning('No hay suficientes observaciones para este número de parámetros.');return
        if np.linalg.matrix_rank(xmat.to_numpy())<xmat.shape[1]:st.warning('Hay colinealidad perfecta o variables constantes. Revisa el diseño.');return
        if kind=='Logístico binario' and set(dat[y].unique())!={0,1}:
            st.warning('La respuesta logística debe contener ambas categorías 0 y 1.');return
        if st.button('Ajustar modelo'):
            try:
                model=(sm.OLS(dat[y],xmat).fit(cov_type='HC3') if kind=='Lineal OLS' else sm.Logit(dat[y],xmat).fit(disp=False))
                if kind=='Logístico binario' and not model.mle_retvals.get('converged',False):
                    st.error('El modelo no convergió; no interpretar sus coeficientes.');return
                ci=model.conf_int()
                result=pd.DataFrame({'termino':model.params.index,'coeficiente':model.params.values,'p':model.pvalues.values,'ic_inferior':ci.iloc[:,0].values,'ic_superior':ci.iloc[:,1].values})
                st.dataframe(result,hide_index=True,use_container_width=True)
                with st.expander('Diagnóstico del ajuste'):st.text(model.summary().as_text())
                csv_button(result,'modelo_multivariable.csv')
                st.warning('Ajuste exploratorio en la muestra, sin validación predictiva externa ni identificación causal. HC3 no corrige dependencia entre visitas de una tienda. Revisa separación, muestreo y tamaño de las clases en logística.')
            except Exception as exc:st.error(f'No se pudo ajustar un modelo válido: {exc}')
        return
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
