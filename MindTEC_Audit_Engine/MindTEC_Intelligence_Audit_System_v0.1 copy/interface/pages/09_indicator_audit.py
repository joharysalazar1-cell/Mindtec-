"""MindTEC v0.4 - Auditoría avanzada (módulo independiente).
Instalar copiando a interface/pages/09_indicator_audit.py.
No altera otros archivos del proyecto.
"""
import io
import json
from datetime import datetime
import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title='MindTEC | Auditoría avanzada', layout='wide')
st.title('09 · Auditoría avanzada de indicadores')
st.caption('Análisis exploratorio independiente · No equivale a validación del dashboard oficial')

@st.cache_data(show_spinner=False)
def read_csv(content: bytes, sep: str, encoding: str):
    return pd.read_csv(io.BytesIO(content), sep=sep, encoding=encoding, low_memory=False)

def numeric(s):
    return pd.to_numeric(s.astype('string').str.replace(',', '.', regex=False), errors='coerce')

def audit_log(msg, level='INFO'):
    st.session_state.setdefault('audit_log', []).append({'fecha': datetime.now().isoformat(timespec='seconds'), 'nivel':level, 'detalle':msg})

def option(label, columns, hints, optional=True):
    opts = ['(ninguna)'] if optional else []
    opts += list(columns)
    default = 0
    for hint in hints:
        for i, col in enumerate(opts):
            if col.lower() == hint.lower():
                default = i
                break
        if default: break
    value = st.selectbox(label, opts, index=default)
    return None if value == '(ninguna)' else value

file = st.file_uploader('Sube un CSV de observaciones (preferiblemente una fila por tienda × producto × período)', type=['csv'])
if file is None:
    st.info('Carga una base de observaciones para activar el diagnóstico. Las bases de facturas por sí solas no permiten auditar caras de estante o quiebres declarados.')
    st.stop()

with st.expander('Lectura del archivo', expanded=False):
    sep = st.selectbox('Separador', [',', ';', '\t', '|'])
    encoding = st.selectbox('Codificación', ['utf-8-sig', 'utf-8', 'latin-1'])
try:
    df = read_csv(file.getvalue(), sep, encoding)
except Exception as exc:
    st.error(f'No se pudo leer el CSV: {exc}')
    st.stop()
if df.empty or not len(df.columns):
    st.error('El archivo no contiene registros utilizables.')
    st.stop()
st.success(f'Archivo cargado: {len(df):,} filas · {len(df.columns)} columnas')

with st.expander('1 · Mapeo de variables y unidad de análisis', expanded=True):
    st.warning('Antes de interpretar los resultados, comprueba la granularidad: tienda, SKU, visita, factura o línea. No mezcles unidades.')
    a,b,c = st.columns(3)
    with a:
        store = option('Identificador de tienda', df.columns, ['tienda_id','codigo_tienda','store_id','tienda'])
        price = option('Precio (Bs)', df.columns, ['precio_bs','precio','precio_venta'])
        shelf_brand = option('Caras de la marca', df.columns, ['caras_marca','faces_brand'])
    with b:
        sku = option('SKU / producto', df.columns, ['sku','producto_id','producto'])
        stockout = option('Quiebre (0/1)', df.columns, ['d_quiebre_stock','quiebre','stockout'])
        shelf_total = option('Caras totales elegibles', df.columns, ['caras_totales','faces_total'])
    with c:
        segment = option('Segmento (canal, zona, etc.)', df.columns, ['canal','tipo_tienda','zona','d_autoservicio'])
        cold = option('Presencia de frío (0/1)', df.columns, ['d_frio','presencia_frio','frio'])
        period = option('Período', df.columns, ['periodo','mes','fecha'])
    st.caption('La selección de columnas no certifica que sus definiciones sean equivalentes a las del dashboard.')

st.subheader('2 · Diagnóstico estructural')
rows = [{'control':'Filas', 'resultado':len(df), 'observación':'Unidad definida por el archivo'},
        {'control':'Columnas', 'resultado':len(df.columns), 'observación':'Variables detectadas'},
        {'control':'Duplicados exactos', 'resultado':int(df.duplicated().sum()), 'observación':'Revisar antes de eliminar'}]
if store:
    rows.append({'control':'Tiendas únicas', 'resultado':int(df[store].nunique(dropna=True)), 'observación':'No equivale necesariamente a tiendas censadas'})
if store and sku and period:
    rows.append({'control':'Duplicados tienda×SKU×período', 'resultado':int(df.duplicated([store,sku,period]).sum()), 'observación':'Pueden ser visitas múltiples legítimas'})
for col in [price,stockout,shelf_brand,shelf_total,cold]:
    if col:
        rows.append({'control':f'Nulos: {col}', 'resultado':int(df[col].isna().sum()), 'observación':f'{df[col].isna().mean():.1%} del archivo'})
st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

issues = []
if price:
    p = numeric(df[price])
    issues.append({'regla':'Precio negativo o cero', 'casos':int((p <= 0).sum()),'denominador':int(p.notna().sum())})
    issues.append({'regla':'Precio no interpretable', 'casos':int(p.isna().sum()),'denominador':len(df)})
if stockout:
    q = numeric(df[stockout])
    issues.append({'regla':'Quiebre fuera de {0,1}', 'casos':int((q.notna() & ~q.isin([0,1])).sum()),'denominador':int(q.notna().sum())})
if cold:
    f = numeric(df[cold])
    issues.append({'regla':'Frío fuera de {0,1}', 'casos':int((f.notna() & ~f.isin([0,1])).sum()),'denominador':int(f.notna().sum())})
if shelf_brand and shelf_total:
    brand, total = numeric(df[shelf_brand]), numeric(df[shelf_total])
    invalid = (brand < 0) | (total <= 0) | (brand > total)
    issues.append({'regla':'Caras inconsistentes', 'casos':int(invalid.fillna(False).sum()),'denominador':int((brand.notna() & total.notna()).sum())})
    valid = brand.notna() & total.notna() & ~invalid
    if valid.any():
        st.subheader('Participación en estante: dos estimandos distintos')
        weighted = brand[valid].sum()/total[valid].sum()
        per_row = (brand[valid]/total[valid]).mean()
        m1,m2 = st.columns(2)
        m1.metric('Participación ponderada por caras',f'{weighted:.1%}')
        m2.metric('Promedio por registro',f'{per_row:.1%}')
        st.caption('El promedio por registro NO es promedio por tienda salvo que cada tienda tenga exactamente un registro elegible. Verifica la unidad de análisis.')
if issues:
    st.dataframe(pd.DataFrame(issues), use_container_width=True, hide_index=True)

st.subheader('3 · Precios atípicos por segmento comparable')
price_anomalies = pd.DataFrame()
if price:
    work = df.copy()
    work['_precio_num'] = numeric(work[price])
    groups = [x for x in [sku, segment] if x]
    if not groups:
        st.warning('Selecciona SKU y/o segmento para evitar comparar productos heterogéneos.')
    else:
        min_n = st.slider('Mínimo de precios válidos por grupo',3,30,5)
        positive = work[work['_precio_num'].gt(0)].copy()
        group_sizes = positive.groupby(groups, dropna=False)['_precio_num'].transform('count')
        q1 = positive.groupby(groups, dropna=False)['_precio_num'].transform(lambda x:x.quantile(.25))
        q3 = positive.groupby(groups, dropna=False)['_precio_num'].transform(lambda x:x.quantile(.75))
        iqr = q3-q1
        positive['_atipico'] = (group_sizes >= min_n) & (iqr > 0) & ((positive['_precio_num'] < q1-1.5*iqr) | (positive['_precio_num'] > q3+1.5*iqr))
        price_anomalies = positive[positive['_atipico']].copy()
        st.metric('Precios atípicos detectados (IQR)',len(price_anomalies))
        st.caption('Grupos pequeños o sin dispersión no se clasifican. Un atípico es una alerta, no necesariamente un error.')
        if len(price_anomalies):
            st.dataframe(price_anomalies[[*groups, price] + ([store] if store and store not in groups else [])].head(300),use_container_width=True)
else:
    st.info('Selecciona una columna de precio para habilitar esta sección.')

st.subheader('4 · Segmentación y asociaciones')
if stockout:
    q = numeric(df[stockout]); valid_q = q.isin([0,1])
    if valid_q.any():
        st.metric('Quiebre declarado por registro válido',f'{q[valid_q].mean():.1%}')
        st.caption('No interpretar como porcentaje de tiendas si existen varios registros por tienda.')
        if segment:
            segment_df = df.loc[valid_q,[segment]].copy()
            segment_df['quiebre'] = q[valid_q]
            summary = segment_df.groupby(segment,dropna=False)['quiebre'].agg(['size','sum','mean']).reset_index()
            summary.columns = [segment,'n_registros','n_quiebres','tasa_quiebre']
            st.dataframe(summary, use_container_width=True, hide_index=True)
        if price:
            p = numeric(df[price]); mask = valid_q & p.gt(0)
            if mask.sum() >= 10 and q[mask].nunique()==2:
                try:
                    from scipy.stats import mannwhitneyu
                    p0,p1 = p[mask & q.eq(0)],p[mask & q.eq(1)]
                    if len(p0)>=3 and len(p1)>=3:
                        stat,pvalue=mannwhitneyu(p0,p1,alternative='two-sided')
                        st.write(f'Precio vs. quiebre · Mann–Whitney U: **p = {pvalue:.4g}**; n₀={len(p0)}, n₁={len(p1)}.')
                        st.caption('Asociación exploratoria; no ajusta por SKU, tienda o canal y no demuestra causalidad.')
                except ImportError:
                    st.info('SciPy no está disponible para esta prueba.')
    else:
        st.warning('No hay valores de quiebre binarios válidos.')
else:
    st.info('Selecciona una variable de quiebre para habilitar análisis de abastecimiento.')

st.subheader('5 · Interacción exploratoria: precio × frío')
if price and stockout and cold:
    if st.button('Estimar modelo logístico exploratorio'):
        try:
            import statsmodels.formula.api as smf
            model_df = pd.DataFrame({'quiebre':numeric(df[stockout]),'precio':numeric(df[price]),'frio':numeric(df[cold])})
            model_df = model_df[model_df['quiebre'].isin([0,1]) & model_df['frio'].isin([0,1]) & model_df['precio'].gt(0)].dropna()
            if len(model_df)<40 or model_df['quiebre'].value_counts().min()<10 or model_df['frio'].nunique()<2:
                st.warning('Muestra o variación insuficiente para una estimación exploratoria estable (mínimo 40 registros y 10 eventos por clase).')
            else:
                model_df['precio_z']=(model_df['precio']-model_df['precio'].mean())/model_df['precio'].std()
                fit=smf.logit('quiebre ~ precio_z * frio',data=model_df).fit(disp=False,maxiter=150)
                result=pd.DataFrame({'coef':fit.params,'odds_ratio':np.exp(fit.params),'p_value':fit.pvalues,'ci_inf_or':np.exp(fit.conf_int()[0]),'ci_sup_or':np.exp(fit.conf_int()[1])})
                st.dataframe(result,use_container_width=True)
                st.caption(f'N={len(model_df)}; precio estandarizado globalmente. Modelo sin controles, sin agrupación por tienda y sujeto a separación. No inferir efectos causales.')
        except Exception as exc:
            st.error(f'No se pudo estimar de forma confiable: {type(exc).__name__}: {exc}')
else:
    st.info('Mapea precio, quiebre y frío para activar el modelo.')

st.subheader('6 · Evidencia y exportación')
metadata = {'archivo':file.name,'filas':len(df),'columnas':list(df.columns),'mapeo':{'tienda':store,'sku':sku,'precio':price,'quiebre':stockout,'caras_marca':shelf_brand,'caras_total':shelf_total,'segmento':segment,'frio':cold,'periodo':period},'controles':rows,'alertas':issues,'fecha':datetime.now().isoformat(timespec='seconds'),'estado':'exploratorio_no_validado'}
st.download_button('Descargar diagnóstico JSON',data=json.dumps(metadata,ensure_ascii=False,indent=2,default=str).encode('utf-8'),file_name='mindtec_diagnostico.json',mime='application/json')
if not price_anomalies.empty:
    st.download_button('Descargar precios atípicos CSV',price_anomalies.to_csv(index=False).encode('utf-8-sig'),file_name='mindtec_precios_atipicos.csv',mime='text/csv')
st.warning('Este primer módulo diagnostica una base cargada. Aún NO reproduce los KPI oficiales ni certifica oportunidad comercial, rotación o causalidad. Para eso faltan reglas de negocio, fuentes y controles de granularidad.')
