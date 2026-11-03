import streamlit as st
import pandas as pd
import plotly.express as px
from src.services.workspace import select_data,csv_button

AREAS=['Distribución y cobertura','Disponibilidad y quiebres','Inventario y stock','Precios','Competencia y participación','Cadencia temporal','Portafolio y surtido','Rendimiento comercial (Sell-in)','Calidad y confiabilidad','Metodología','Predicción y modelos','Predicción operativa tienda-producto']

def render():
    st.title('🏪 Inteligencia comercial')
    st.caption('Las 12 aristas son preguntas de investigación, no indicadores calculables automáticamente.')
    area=st.selectbox('Arista de investigación',AREAS)
    df,_=select_data(key='intel')
    if df is None:return
    st.info('Selecciona las variables que representan el fenómeno. No se infiere su significado por el nombre.')
    if area=='Calidad y confiabilidad':
        quality=pd.DataFrame({'variable':df.columns,'nulos':df.isna().sum().values,'porcentaje_nulos':(df.isna().mean()*100).round(2).values,'unicos':df.nunique().values})
        st.dataframe(quality,use_container_width=True,hide_index=True)
        st.metric('Filas exactamente duplicadas',int(df.duplicated().sum()))
        csv_button(quality,'calidad.csv');return
    if area=='Metodología':
        st.write('Registros:',len(df),' · Variables:',len(df.columns))
        st.warning('Para inferencia poblacional se requieren diseño de muestra, marco, unidades, conglomerados y factores de expansión cuando correspondan.')
        return
    if area in ('Predicción y modelos','Predicción operativa tienda-producto'):
        st.info('Los modelos predictivos se configuran en Modelos estadísticos. Debe verificarse la unidad de observación y disponibilidad de variable objetivo.')
        return
    group=st.selectbox('Dimensión / categoría',list(df.columns),key='intel_group')
    numeric=list(df.select_dtypes(include='number').columns)
    measure=st.selectbox('Medida', ['Conteo de registros']+numeric,key='intel_measure')
    if measure=='Conteo de registros':
        result=df.groupby(group,dropna=False).size().reset_index(name='conteo')
        val='conteo'
    else:
        op=st.selectbox('Agregación',['suma','promedio','mediana'],key='intel_agg')
        fn={'suma':'sum','promedio':'mean','mediana':'median'}[op]
        result=df.groupby(group,dropna=False)[measure].agg(fn).reset_index(name=measure)
        val=measure
    result=result.sort_values(val,ascending=False)
    st.dataframe(result,use_container_width=True,hide_index=True)
    st.plotly_chart(px.bar(result.head(30),x=group,y=val,title=area),use_container_width=True)
    csv_button(result,'inteligencia_comercial.csv')
    st.warning('Este cálculo es una agregación exploratoria. No equivale automáticamente a cobertura, cuota de mercado, quiebre, inventario o Sell-in; verifica la definición, denominador y granularidad.')
