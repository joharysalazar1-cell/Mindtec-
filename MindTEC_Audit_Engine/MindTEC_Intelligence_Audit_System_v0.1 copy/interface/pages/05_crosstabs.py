import streamlit as st
import pandas as pd
import numpy as np
from scipy.stats import chi2_contingency, fisher_exact
from src.services.workspace import select_data, csv_button

MAX_CELLS = 2500


def _categorias(df, cols, incluir_faltantes):
    out = df[cols].copy()
    for c in cols:
        out[c] = out[c].astype('string')
        if incluir_faltantes:
            out[c] = out[c].fillna('(Sin dato)')
    if not incluir_faltantes:
        out = out.dropna(subset=cols)
    return out


def _tabla(df, fila, columna, modalidades, totales):
    frecuencias = pd.crosstab(df[fila], df[columna], dropna=False)
    if frecuencias.empty:
        return None, None
    total = frecuencias.to_numpy().sum()
    if total == 0:
        return None, None
    salidas = {}
    if 'Recuento observado' in modalidades:
        salidas['Recuento observado'] = frecuencias
    if '% por fila' in modalidades:
        salidas['% por fila'] = frecuencias.div(frecuencias.sum(axis=1).replace(0, np.nan), axis=0) * 100
    if '% por columna' in modalidades:
        salidas['% por columna'] = frecuencias.div(frecuencias.sum(axis=0).replace(0, np.nan), axis=1) * 100
    if '% del total' in modalidades:
        salidas['% del total'] = frecuencias / total * 100
    if 'Recuento esperado' in modalidades:
        esperado = np.outer(frecuencias.sum(axis=1), frecuencias.sum(axis=0)) / total
        salidas['Recuento esperado'] = pd.DataFrame(esperado, index=frecuencias.index, columns=frecuencias.columns)
    return frecuencias, salidas


def _mostrar_estadisticas(counts, fisher):
    if min(counts.shape) < 2:
        st.info('No se puede calcular asociación: alguna variable solo tiene una categoría observada.')
        return
    try:
        chi, p, gl, expected = chi2_contingency(counts, correction=False)
    except ValueError as exc:
        st.warning(f'No se pudo calcular chi-cuadrado: {exc}')
        return
    n = counts.to_numpy().sum()
    k = min(counts.shape) - 1
    v = np.sqrt(chi / (n * k)) if n > 0 and k > 0 else np.nan
    st.dataframe(pd.DataFrame([
        {'Estadístico': 'Chi-cuadrado de Pearson', 'Valor': chi, 'gl': gl, 'p': p},
        {'Estadístico': 'V de Cramér', 'Valor': v, 'gl': np.nan, 'p': np.nan},
    ]), hide_index=True, use_container_width=True)
    bajo5 = int((expected < 5).sum())
    bajo1 = int((expected < 1).sum())
    st.caption(f'N válido = {n:,}. Frecuencias esperadas <5: {bajo5}/{expected.size}; <1: {bajo1}/{expected.size}.')
    if bajo5 / expected.size > 0.2 or bajo1:
        st.warning('Advertencia: frecuencias esperadas pequeñas; el valor p asintótico puede ser poco fiable.')
    if fisher and counts.shape == (2, 2):
        odds, pf = fisher_exact(counts.to_numpy())
        st.write(f'**Prueba exacta de Fisher (bilateral):** p = {pf:.6g}; odds ratio = {odds:.6g}')
    st.caption('Análisis exploratorio sin ponderaciones ni ajuste por diseño muestral. Asociación no demuestra causalidad.')


def render():
    st.title('🔀 Tablas cruzadas · estilo SPSS')
    st.caption('Selecciona múltiples variables de filas y columnas, estratifica por una capa y configura las celdas.')
    df, _ = select_data(key='cross')
    if df is None:
        return
    columnas = list(df.columns)
    if len(columnas) < 2:
        st.info('Se requieren al menos dos variables.')
        return

    c1, c2 = st.columns(2)
    with c1:
        filas = st.multiselect('Filas (una o varias variables)', columnas, default=[columnas[0]], key='ct_rows')
    with c2:
        cols = st.multiselect('Columnas (una o varias variables)', columnas, default=[columnas[1]], key='ct_cols')
    capa = st.selectbox('Capa / variable de control (opcional)', ['(Sin capa)'] + columnas, key='ct_layer')
    capa = None if capa == '(Sin capa)' else capa
    with st.expander('Opciones de celdas y pruebas', expanded=True):
        modalidades = st.multiselect('Mostrar en cada cruce', ['Recuento observado', 'Recuento esperado', '% por fila', '% por columna', '% del total'], default=['Recuento observado', '% por fila', '% por columna'], key='ct_cells')
        incluir_faltantes = st.checkbox('Incluir valores perdidos como categoría (Sin dato)', value=False)
        mostrar_estadisticas = st.checkbox('Chi-cuadrado de Pearson y V de Cramér', value=True)
        fisher = st.checkbox('Prueba exacta de Fisher para tablas 2 × 2', value=True)
        mostrar_totales = st.checkbox('Mostrar totales para recuentos', value=True)
        limite = st.number_input('Máximo de categorías distintas por variable', min_value=2, max_value=1000, value=60, step=10)

    if not filas or not cols or not modalidades:
        st.info('Selecciona al menos una variable en filas, una en columnas y una modalidad de celdas.')
        return
    pares = [(a, b) for a in filas for b in cols]
    if any(a == b for a, b in pares):
        st.error('No cruces una variable consigo misma: quita las variables repetidas entre filas y columnas.')
        return
    if capa and capa in set(filas + cols):
        st.error('La variable de capa debe ser distinta de las variables de filas y columnas.')
        return
    if len(pares) > 30:
        st.warning('Se permiten como máximo 30 cruces por ejecución para proteger el rendimiento.')
        return
    if not st.button('▶ Ejecutar tablas cruzadas', type='primary'):
        return

    for a, b in pares:
        st.divider()
        st.subheader(f'{a} × {b}')
        seleccion = [a, b] + ([capa] if capa else [])
        valid = _categorias(df, seleccion, incluir_faltantes)
        st.caption(f'Registros en fuente: {len(df):,} · Registros válidos para este cruce: {len(valid):,} · Excluidos: {len(df)-len(valid):,}')
        if valid.empty:
            st.warning('Sin observaciones válidas para este cruce.')
            continue
        if any(valid[c].nunique(dropna=False) > limite for c in seleccion):
            st.warning('Demasiadas categorías para visualizar con seguridad. Cambia de variables o aumenta el límite con precaución.')
            continue
        grupos = [('Total', valid)]
        if capa:
            grupos = [(str(valor), grupo) for valor, grupo in valid.groupby(capa, dropna=False, sort=False)]
            if len(grupos) > 50:
                st.warning('Más de 50 estratos: elige una capa con menos categorías.')
                continue
        for etiqueta, subset in grupos:
            if capa:
                st.markdown(f'**{capa}: {etiqueta}** · N = {len(subset):,}')
            counts, salidas = _tabla(subset, a, b, modalidades, mostrar_totales)
            if counts is None:
                st.info('Sin categorías observadas.')
                continue
            if counts.size > MAX_CELLS:
                st.warning(f'Tabla demasiado grande ({counts.size:,} celdas).')
                continue
            for titulo, tabla in salidas.items():
                st.markdown(f'**{titulo}**')
                if titulo == 'Recuento observado' and mostrar_totales:
                    vista = tabla.copy()
                    vista['Total'] = vista.sum(axis=1)
                    vista.loc['Total'] = vista.sum(axis=0)
                else:
                    vista = tabla
                st.dataframe(vista, use_container_width=True)
                export = vista.reset_index()
                csv_button(export, f'crosstab_{len(a)}_{len(b)}_{titulo.replace(" ", "_")}.csv')
            if mostrar_estadisticas:
                _mostrar_estadisticas(counts, fisher)
