import io
import pandas as pd
import streamlit as st


def sources():
    return st.session_state.get('archivos_cargados', {})


def get_df(key, sheet=None):
    r = sources()[key]
    raw = io.BytesIO(r['contenido'])
    if r['extension'].lower() == 'csv':
        for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):
            try:
                raw.seek(0)
                return pd.read_csv(raw, sep=None, engine='python', encoding=enc)
            except UnicodeDecodeError:
                continue
        raise ValueError('No se pudo decodificar el CSV.')
    return pd.read_excel(raw, sheet_name=sheet or 0)


def select_data(label='Fuente de datos', key='source'):
    data = sources()
    if not data:
        st.info('Primero incorpora archivos en Cargar bases de datos.')
        return None, None
    ids = list(data)
    choice = st.selectbox(label, ids, format_func=lambda i: data[i]['nombre'] + ' · ' + i[:8], key=key)
    record = data[choice]
    sheet = None
    if record.get('hojas'):
        sheet = st.selectbox('Hoja de Excel', record['hojas'], key=key+'_sheet')
    record['hoja_seleccionada'] = sheet
    try:
        df = get_df(choice, sheet)
        if df.empty or not len(df.columns):
            st.warning('Esta fuente no contiene registros analizables.')
            return None, None
        return df, choice
    except Exception as exc:
        st.error(f'No se pudo leer la fuente: {exc}')
        return None, None


def csv_button(df, name='resultados.csv'):
    st.download_button('⬇ Exportar CSV', df.to_csv(index=False).encode('utf-8-sig'), name, 'text/csv')


def variables(df, numeric=False):
    if numeric:
        return list(df.select_dtypes(include='number').columns)
    return list(df.columns)
