import pandas as pd
import streamlit as st
from src.audit_core import quality_report, reconcile, ratio_metric
from src.services.workspace import select_data, sources, csv_button


def save_result(title, table, metadata):
    st.session_state.setdefault('audit_results', {})[title] = {
        'tabla':table.copy(), 'metadata':metadata,
        'fecha':pd.Timestamp.now(tz='UTC').isoformat()}


def describe_source(source_id, prefix):
    record = sources()[source_id]
    st.caption('SHA-256: ' + source_id)
    meta = st.session_state.setdefault('source_metadata', {}).setdefault(source_id,{})
    meta['rol'] = st.selectbox('Rol de la fuente', ['Base analítica','Dashboard exportado','Observación de campo','Declaración','Facturas','Referencia externa'],key=prefix+'_role')
    meta['version'] = st.text_input('Versión / fecha de corte',meta.get('version',''),key=prefix+'_version')
    meta['periodo'] = st.text_input('Periodo que representa',meta.get('periodo',''),key=prefix+'_period')
    meta['procedencia'] = st.text_input('Procedencia y alcance',meta.get('procedencia',record['nombre']),key=prefix+'_origin')
    return dict(meta, archivo=record['nombre'], sha256=source_id, hoja=record.get('hoja_seleccionada'))


def audit():
    st.title('Auditoría de la base')
    st.caption('Comprueba integridad antes de interpretar indicadores. Las alertas no corrigen ni eliminan datos.')
    df,sid = select_data(key='audit_source')
    if df is None:return
    meta = describe_source(sid,'audit_meta')
    unit = st.text_input('Unidad de observación',placeholder='Ej.: una línea de factura, una tienda × SKU × visita')
    keys = st.multiselect('Columnas que identifican una observación',list(df.columns))
    report = quality_report(df,keys)
    a,b,c=st.columns(3)
    a.metric('Filas',len(df)); b.metric('Variables',len(df.columns)); c.metric('Duplicados exactos',int(df.duplicated().sum()))
    st.dataframe(report,hide_index=True,use_container_width=True)
    if keys:
        flagged=df[df[keys].isna().any(axis=1)|df.duplicated(keys,keep=False)]
        with st.expander('Registros con clave incompleta o repetida'):
            st.dataframe(flagged,use_container_width=True)
    if st.button('Guardar diagnóstico en Resultados'):
        save_result('Diagnóstico · '+sources()[sid]['nombre'],report,dict(meta,unidad=unit,claves=keys));st.success('Diagnóstico guardado en esta sesión.')
    csv_button(report,'diagnostico_base.csv')


def contrast():
    st.title('Contraste de fuentes e indicadores')
    st.caption('Compara un export del dashboard, una fuente adicional o una referencia contra la base seleccionada.')
    left,lid=select_data('Base a auditar',key='compare_left')
    right,rid=select_data('Fuente de contraste',key='compare_right')
    if left is None or right is None:return
    if lid==rid:st.info('Selecciona dos archivos diferentes.');return
    c1,c2=st.columns(2)
    with c1:
        lm=describe_source(lid,'cmp_l')
        lk=st.multiselect('Claves de la base, en orden',list(left.columns),key='cmp_lk')
        lv=st.selectbox('Medida de la base',list(left.columns),key='cmp_lv')
    with c2:
        rm=describe_source(rid,'cmp_r')
        rk=st.multiselect('Claves de referencia, en el mismo orden',list(right.columns),key='cmp_rk')
        rv=st.selectbox('Medida de referencia',list(right.columns),key='cmp_rv')
    st.info('Para indicadores usa una fila por indicador y segmento, con su valor numérico. Incluye periodo, marca, canal y categoría en las claves cuando correspondan. Las claves se comparan como texto exacto; no se cambian nombres ni alias.')
    scope=st.text_area('Definición común: fórmula, unidad, filtros, exclusiones y denominador')
    absolute=st.number_input('Tolerancia absoluta (misma unidad)',min_value=0.0,value=0.0)
    relative=st.number_input('Tolerancia relativa (%)',min_value=0.0,value=0.0)
    ready=st.checkbox('Confirmo que periodo, unidad, fórmula y universo son comparables')
    if st.button('Ejecutar contraste',type='primary'):
        if not ready or not scope.strip() or not lm['periodo'].strip() or not rm['periodo'].strip():
            st.warning('Documenta periodos y definición, y confirma la comparabilidad antes de ejecutar.');return
        try:
            result=reconcile(left,right,lk,rk,lv,rv,absolute,relative/100)
        except ValueError as exc:st.error(str(exc));return
        save_result('Contraste · '+sources()[lid]['nombre']+' vs '+sources()[rid]['nombre'],result,dict(base=lm,referencia=rm,definicion=scope,claves_base=lk,claves_referencia=rk,medida_base=lv,medida_referencia=rv,tolerancia_absoluta=absolute,tolerancia_relativa_pct=relative))
        st.success('Contraste guardado. Revisa el detalle en Resultados y hallazgos.')
        st.dataframe(result,hide_index=True,use_container_width=True)
    st.caption('Diferencia = base − referencia. Porcentaje = diferencia / referencia; si referencia = 0 se deja sin porcentaje. La tolerancia combina margen absoluto + relativo × |referencia|. Una discrepancia no demuestra cuál fuente es correcta.')


def indicators():
    st.title('Indicadores con denominador explícito')
    st.caption('Calcula desde la evidencia. La selección de columnas debe corresponder a la definición comercial.')
    df,sid=select_data(key='metric_source')
    if df is None:return
    name=st.text_input('Nombre del indicador',placeholder='Presencia Pil, share de estante, quiebre declarado…')
    definition=st.text_area('Definición, periodo, filtros y exclusiones',key='metric_definition')
    mode=st.radio('Unidad del cálculo',['Tiendas','Caras / cantidades'],horizontal=True)
    cols=list(df.columns)
    if mode=='Tiendas':
        entity=st.selectbox('Identificador de tienda',cols)
        eligible=st.selectbox('Columna que define elegibilidad',cols)
        eligible_value=st.selectbox('Valor elegible',df[eligible].dropna().astype(str).unique().tolist())
        num=st.selectbox('Columna de presencia / condición',cols)
        den=st.selectbox('Valor que cumple la condición',df[num].dropna().astype(str).unique().tolist())
        st.caption('Denominador: tiendas únicas elegibles. Numerador: tiendas elegibles con al menos una fila que cumple la condición.')
    else:
        num=st.selectbox('Columna numerador',cols)
        den=st.selectbox('Columna denominador',cols)
        entity=eligible=eligible_value=None
        st.warning('Cada fila debe contener numerador y denominador de la misma unidad. No uses totales repetidos al unir tablas.')
    confirmed=st.checkbox('He verificado la unidad y que no hay denominadores duplicados')
    if st.button('Calcular indicador',type='primary'):
        if not name.strip() or not definition.strip() or not confirmed:
            st.warning('Completa la definición y verifica la unidad antes de calcular.');return
        try:n,d,v=ratio_metric(df,mode,num,den,entity,eligible,eligible_value)
        except ValueError as exc:st.error(str(exc));return
        result=pd.DataFrame([dict(indicador=name,numerador=n,denominador=d,valor_pct=v)])
        st.metric(name,f'{v:.2f} %');st.write(f'Numerador: {n:g} · Denominador: {d:g}')
        save_result('Indicador · '+name,result,dict(sha256=sid,hoja=sources()[sid].get('hoja_seleccionada'),definicion=definition,modo=mode,numerador=num,denominador=den,entidad=entity,elegibilidad=eligible,valor_elegible=eligible_value))


def results():
    import json
    st.title('Resultados y hallazgos')
    items=st.session_state.get('audit_results',{})
    st.caption('Resultados reproducibles de esta sesión. Descarga el expediente para conservarlo al cerrar la aplicación.')
    if not items:st.info('Ejecuta una auditoría, un contraste o un indicador para generar evidencia.');return
    title=st.selectbox('Evidencia',list(items))
    item=items[title]
    st.dataframe(item['tabla'],use_container_width=True,hide_index=True)
    if 'estado' in item['tabla']:
        st.bar_chart(item['tabla']['estado'].value_counts())
    with st.expander('Procedencia y reglas del cálculo'):st.json(item['metadata'])
    csv_button(item['tabla'],'evidencia_auditoria.csv')
    findings=st.session_state.setdefault('audit_findings',{})
    prior=findings.get(title,{})
    interpretation=st.text_area('Interpretación y evidencia adicional',prior.get('interpretacion',''),key='finding_'+title)
    limitations=st.text_area('Limitaciones / información pendiente',prior.get('limitaciones',''),key='limits_'+title)
    action=st.text_area('Recomendación',prior.get('recomendacion',''),key='action_'+title)
    status=st.selectbox('Resolución del analista',['Pendiente','Diferencia explicada','Error confirmado en base','Error confirmado en referencia','No verificable'],key='resolution_'+title)
    if st.button('Guardar hallazgo'):
        findings[title]=dict(interpretacion=interpretation,limitaciones=limitations,recomendacion=action,resolucion=status)
        st.success('Hallazgo guardado en la sesión.')
    payload=dict(titulo=title,fecha=item['fecha'],reglas=item['metadata'],evidencia=json.loads(item['tabla'].to_json(orient='records')),hallazgo=findings.get(title,{}))
    st.download_button('Descargar expediente JSON',json.dumps(payload,ensure_ascii=False,indent=2).encode('utf-8'),'expediente_auditoria.json','application/json')
