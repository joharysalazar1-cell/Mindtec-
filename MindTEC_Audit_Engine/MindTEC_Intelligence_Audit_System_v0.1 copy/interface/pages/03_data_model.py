import streamlit as st
import pandas as pd
from src.services.workspace import sources, get_df

def render():
    st.title('🧩 Modelo de datos')
    data = sources()
    if not data:
        st.info('Carga al menos un archivo.'); return
    rows=[]
    for k,r in data.items():
        try:
            df=get_df(k)
            rows.append({'fuente':r['nombre'],'id':k[:10],'filas':len(df),'columnas':len(df.columns),'variables':', '.join(map(str,df.columns))})
        except Exception as e: rows.append({'fuente':r['nombre'],'error':str(e)})
    st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)
    st.warning('No se combinan tablas automáticamente. Una coincidencia de nombre no demuestra una relación válida.')
    if len(data)<2: return
    keys=list(data)
    left=st.selectbox('Tabla izquierda',keys,format_func=lambda k:data[k]['nombre']+' · '+k[:8],key='model_left')
    right=st.selectbox('Tabla derecha',keys,index=1,format_func=lambda k:data[k]['nombre']+' · '+k[:8],key='model_right')
    if left==right:
        st.info('Elige dos fuentes diferentes.'); return
    try:
        a,b=get_df(left),get_df(right)
        lc=st.selectbox('Clave izquierda',list(a.columns)); rc=st.selectbox('Clave derecha',list(b.columns))
        al=a[lc].dropna(); bl=b[rc].dropna()
        x,y,z=st.columns(3)
        x.metric('Duplicados clave izquierda',int(al.duplicated().sum()))
        y.metric('Duplicados clave derecha',int(bl.duplicated().sum()))
        z.metric('Nulos en ambas claves',int(a[lc].isna().sum()+b[rc].isna().sum()))
        st.write('Coincidencias entre claves (comparación textual, sin alterar las fuentes):',len(set(al.astype(str)) & set(bl.astype(str))))
        st.caption('Esto es diagnóstico, no una unión. Revisa granularidad, tipos, identificadores y cardinalidad antes de definir relaciones.')
    except Exception as e: st.error(str(e))
