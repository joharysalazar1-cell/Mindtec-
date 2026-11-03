import streamlit as st
import pandas as pd
import hashlib
import io
from src.source_checks import PROFILES, check_source, register_upload
from src.services.source_history import save_snapshot, list_snapshots, restore_snapshot


def identificar_archivo(archivo):
    """Identifica un archivo mediante su contenido."""

    contenido = archivo.getvalue()

    identificador = hashlib.sha256(contenido).hexdigest()

    return identificador


def obtener_hojas_excel(contenido):
    """Obtiene los nombres de las hojas de un Excel."""

    excel = pd.ExcelFile(io.BytesIO(contenido))

    return excel.sheet_names


def leer_archivo(contenido, nombre, hoja=None):
    """Lee un archivo sin modificar su contenido original."""

    extension = nombre.lower().split(".")[-1]

    if extension == "csv":

        errores = []

        for encoding in ["utf-8", "utf-8-sig", "latin-1"]:
            try:
                return pd.read_csv(
                    io.BytesIO(contenido),
                    encoding=encoding,
                    sep=None,
                    engine="python"
                )
            except Exception as error:
                errores.append(str(error))

        raise ValueError("No fue posible interpretar el archivo CSV.")

    elif extension in ["xlsx", "xls"]:

        return pd.read_excel(
            io.BytesIO(contenido),
            sheet_name=hoja
        )

    else:
        raise ValueError("Formato de archivo no compatible.")


def pagina_recepcion_datos():

    st.title("📂 Cargar y verificar bases de datos")

    st.caption(
        "Carga tus bases originales, identifica su función y comprueba si contienen los campos necesarios."
    )

    st.divider()
    with st.expander('Recuperar una base guardada en este equipo'):
        history=list_snapshots()
        if history:
            names=[name for name,_ in history]
            descriptions={name:f"{entry.get('nombre','Archivo')} · {entry.get('metadata',{}).get('periodo','sin periodo')} · {entry.get('guardado_utc','')}" for name,entry in history}
            selected=st.selectbox('Versión guardada',names,format_func=lambda k:descriptions[k])
            if st.button('Recuperar versión en la sesión'):
                try:restore_snapshot(selected,st.session_state);st.success('Base recuperada; disponible en los módulos.')
                except Exception as exc:st.error(f'No se pudo recuperar: {exc}')
        else:st.caption('Todavía no hay bases guardadas localmente.')
    st.info('Para contrastar el tablero completo necesitas censo de campo, facturas y líneas, catálogos y export de indicadores del mismo periodo. El control de envíos no sustituye el censo.')

    # INICIALIZAR REGISTRO DE SESIÓN
    if "archivos_cargados" not in st.session_state:
        st.session_state.archivos_cargados = {}

    # CARGADOR
    st.subheader("1. Incorporar archivos")

    archivos = st.file_uploader(
        "Selecciona uno o varios archivos",
        type=["csv", "xlsx", "xls"],
        accept_multiple_files=True,
        help="Puedes cargar múltiples archivos simultáneamente."
    )

    if archivos:

        for archivo in archivos:

            contenido = archivo.getvalue()

            identificador = identificar_archivo(archivo)

            if identificador not in st.session_state.archivos_cargados:

                extension = archivo.name.lower().split(".")[-1]

                registro = {"hojas":None}

                if extension in ["xlsx", "xls"]:
                    try:
                        registro["hojas"] = obtener_hojas_excel(
                            contenido
                        )
                    except Exception as error:
                        registro["error"] = str(error)

                register_upload(st.session_state,archivo.name,contenido,registro['hojas'])
                if registro.get('error'):
                    st.session_state.archivos_cargados[identificador]['error']=registro['error']
                st.success(f'Base incorporada: {archivo.name}')

    st.divider()

    # REGISTRO DE ARCHIVOS
    st.subheader("2. Archivos incorporados")

    registros = st.session_state.archivos_cargados

    if not registros:

        st.info("Todavía no se han incorporado archivos.")

    else:

        total_archivos = len(registros)

        total_bytes = sum(
            registro["tamano"]
            for registro in registros.values()
        )

        col1, col2 = st.columns(2)

        col1.metric("Archivos incorporados", total_archivos)

        col2.metric(
            "Tamaño total",
            f"{total_bytes / 1024:.2f} KB"
        )

        st.divider()

        # SELECCIÓN DE ARCHIVO
        identificadores = list(registros.keys())

        id_seleccionado = st.selectbox(
            "Selecciona un archivo para explorar",
            identificadores,
            format_func=lambda k:registros[k]['nombre']+' · '+k[:8]
        )

        registro = registros[id_seleccionado]

        st.write(f"**Nombre:** {registro['nombre']}")
        st.write(f"**Formato:** {registro['extension'].upper()}")
        st.write(
            f"**Tamaño:** {registro['tamano'] / 1024:.2f} KB"
        )

        # PREVISUALIZACIÓN
        st.subheader("3. Vista previa")

        hoja_seleccionada = None

        if registro["hojas"]:

            hoja_seleccionada = st.selectbox(
                "Selecciona una hoja",
                registro["hojas"]
            )

        try:

            df = leer_archivo(
                registro["contenido"],
                registro["nombre"],
                hoja_seleccionada
            )

            if not isinstance(df, pd.DataFrame):
                st.warning("No se pudo interpretar la hoja seleccionada.")
            else:

                col1, col2, col3 = st.columns(3)

                col1.metric("Registros", f"{len(df):,}")
                col2.metric("Variables", f"{len(df.columns):,}")
                col3.metric("Duplicados exactos", int(df.duplicated().sum()))
                st.subheader('¿Esta base sirve para el análisis?')
                metadata=st.session_state.setdefault('source_metadata',{}).setdefault(id_seleccionado,{})
                roles=list(PROFILES)
                role=st.selectbox('Tipo de base',roles,index=roles.index(metadata['tipo_base']) if metadata.get('tipo_base') in roles else 0,key='upload_role_'+id_seleccionado)
                metadata['tipo_base']=role
                metadata['periodo']=st.text_input('Periodo / ola de la base',metadata.get('periodo',''),key='upload_period_'+id_seleccionado,placeholder='Ej.: octubre 2026 o fechas de inicio y fin')
                metadata['procedencia']=st.text_input('Procedencia',metadata.get('procedencia',''),key='upload_origin_'+id_seleccionado)
                metadata['unidad']=st.text_input('Una fila representa…',metadata.get('unidad',''),key='upload_unit_'+id_seleccionado,placeholder='Una factura, una línea, una tienda × producto × visita…')
                metadata['hoja']=hoja_seleccionada
                checks=check_source(df,role)
                if df.empty:st.error('La base no contiene registros analizables.')
                elif checks.empty:st.info('Referencia externa: documenta sus claves, alcance y comparabilidad antes de contrastarla.')
                else:
                    st.dataframe(checks,hide_index=True,width='stretch')
                    if checks.estado.eq('Detectado').all():
                        st.success('Estructura compatible con el tipo seleccionado. Aún debes validar contenido, periodo y reglas de negocio.')
                    else:st.warning('Faltan campos reconocibles para este uso. Puede requerir mapear nombres distintos o incorporar otra fuente; no implica que el archivo sea incorrecto.')
                st.caption('La revisión reconoce nombres de columnas sin renombrar ni modificar tus datos. No certifica exactitud ni equivalencia con el dashboard.')
                with st.expander('Revisar fechas y posibles registros fuera del corte'):
                    from datetime import datetime,timezone,timedelta
                    date_col=st.selectbox('Columna de fecha',[None]+list(df.columns),format_func=lambda c:c or 'Seleccionar',key='date_col_'+id_seleccionado)
                    if date_col:
                        cutoff=st.date_input('Fecha de corte',datetime.now(timezone(timedelta(hours=-4))).date(),key='date_cut_'+id_seleccionado)
                        parsed=pd.to_datetime(df[date_col],errors='coerce',format='mixed',utc=True)
                        nonempty=df[date_col].notna()
                        bad=nonempty & parsed.isna()
                        future=parsed.dt.date.gt(cutoff).fillna(False)
                        st.write(f'No interpretables: {int(bad.sum())} · Posteriores al corte: {int(future.sum())} · Sin fecha: {int((~nonempty).sum())}')
                        st.caption('Comprueba el orden día/mes del archivo. Fechas fuera del corte son alertas; no se corrigen automáticamente.')
                        if (bad|future).any():st.dataframe(df.loc[bad|future],hide_index=True,width='stretch')
                if role in ('Facturas','Líneas de factura','Control de envíos','Catálogo de productos','Catálogo de distribuidores'):
                    st.info('Esta fuente no basta por sí sola para auditar caras de estante, equipos de frío o quiebre declarado. Para eso necesitas el censo detallado.')
                if st.button('Guardar original y periodo en historial local',key='save_upload_'+id_seleccionado):
                    if not metadata['periodo'].strip():st.warning('Indica el periodo antes de guardar esta versión.')
                    else:
                        try:save_snapshot(registro,dict(metadata));st.success('Original guardado en este equipo. No se sube a GitHub.')
                        except OSError:st.error('No se pudo guardar. Comprueba el permiso de escritura del directorio de datos.')

                st.dataframe(
                    df.head(100),
                    use_container_width=True,
                    hide_index=True
                )

                with st.expander("Consultar estructura de variables"):

                    estructura = pd.DataFrame({
                        "Variable": df.columns,
                        "Tipo de dato": df.dtypes.astype(str).values,
                        "Valores no nulos": df.notna().sum().values
                    })

                    st.dataframe(
                        estructura,
                        use_container_width=True,
                        hide_index=True
                    )

        except Exception as error:

            st.error(f"Error al leer el archivo: {error}")

        st.divider()

        # RETIRAR ARCHIVO DE SESIÓN
        st.subheader("4. Administración")

        if st.button(
            "Retirar archivo seleccionado de esta sesión",
            type="secondary"
        ):

            del st.session_state.archivos_cargados[
                id_seleccionado
            ]

            st.rerun()

        st.caption(
            "Retirar un archivo de esta sesión no elimina ni modifica "
            "el archivo original de tu computadora."
        )
