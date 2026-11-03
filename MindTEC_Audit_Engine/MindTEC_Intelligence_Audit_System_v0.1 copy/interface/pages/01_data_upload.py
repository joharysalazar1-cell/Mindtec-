import streamlit as st
import pandas as pd
import hashlib
import io


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

    st.title("📂 Recepción de datos")

    st.caption(
        "Incorporación y administración de fuentes de información."
    )

    st.divider()

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

                registro = {
                    "nombre": archivo.name,
                    "extension": extension,
                    "tamano": len(contenido),
                    "contenido": contenido,
                    "hojas": None
                }

                if extension in ["xlsx", "xls"]:
                    try:
                        registro["hojas"] = obtener_hojas_excel(
                            contenido
                        )
                    except Exception as error:
                        registro["error"] = str(error)

                st.session_state.archivos_cargados[
                    identificador
                ] = registro

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

        opciones = {
            registros[id_archivo]["nombre"]: id_archivo
            for id_archivo in identificadores
        }

        nombre_seleccionado = st.selectbox(
            "Selecciona un archivo para explorar",
            list(opciones.keys())
        )

        id_seleccionado = opciones[nombre_seleccionado]

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
                col3.metric("Columnas", len(df.columns))

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
