import streamlit as st
from src.services.auto_sources import synchronize


def render():
    st.title('Fuentes automáticas')
    st.write('Los endpoints configurados se consultan al abrir la app y se vuelven a revisar mientras está abierta. Cada fuente queda disponible en los módulos de análisis.')
    force=st.button('Actualizar fuentes ahora')
    try:config,changed=synchronize(st.session_state,force=force)
    except Exception:
        st.error('No se pudo leer la configuración local. Revisa config/sources.local.json.');return
    if not config:
        st.info('Conector preparado. Falta configurar endpoint, autenticación y estructura de respuesta.')
    else:
        st.dataframe(list(st.session_state.get('api_status',{}).values()),hide_index=True,use_container_width=True)
    st.subheader('Configurar la conexión')
    st.markdown('Define **MINDTEC_API_URL** y **MINDTEC_API_KEY** en el entorno del servidor. Para varias fuentes, copia `config/sources.example.json` como `config/sources.local.json` y configura una entrada por endpoint. Ese archivo local está excluido de Git.')
    st.caption('Compatible con GET HTTPS, CSV UTF-8 o JSON de registros. Para JSON anidado configura records_path, por ejemplo data.items. El encabezado y el prefijo de autenticación son configurables. No se envían datos locales a la API.')
    st.warning('La API debe devolver un export completo y acotado. Si usa paginación, OAuth o un esquema distinto, el adaptador requiere ajustarse a su contrato. Ante fallos se conserva la última fuente y se marca su estado. El servidor Streamlit debe estar activo; GitHub no ejecuta la extracción.')
