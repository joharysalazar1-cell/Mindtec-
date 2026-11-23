# MindTEC · interfaz visual unificada

Esta rama aporta un estilo visual de dashboard (marino, naranja, tarjetas, tablas y navegación lateral) a **todos los módulos Streamlit**, sin reemplazar sus cálculos ni inventar los 12 KPI oficiales.

## Pantallas nuevas

- **Inicio**: portada ejecutiva con indicadores reales de la sesión (fuentes demo/reales, expedientes, hallazgos) y accesos rápidos.
- **Dashboard ejecutivo**: resume los resultados guardados por el auditor en `st.session_state`, presenta KPI calculados de forma verificable y una matriz de expedientes/hallazgos. Si no hay un KPI, no muestra ceros inventados.
- **Dashboard HTML original**: abre de modo local y con confirmación explícita uno de estos archivos, si existe:
  - `dashboard-html/dist/MindTEC_Dashboard_con_auditoria_y_trazabilidad.html` en el repositorio
  - `INFORME_MINDTEC_COMPLETO.html` en la raíz del repositorio (reporte local ya preparado por el usuario)

La vista HTML permanece **estática**: abrirla no conecta la API, no sincroniza el estado con Streamlit y no verifica matemáticamente los 12 KPI.

## Instalar la rama en Windows

Desde la raíz del repositorio, sin borrar los archivos locales no rastreados:

```powershell
git status
git fetch origin
git switch --track origin/feature/streamlit-visual-dashboard
```

Si esa rama ya existe localmente:

```powershell
git switch feature/streamlit-visual-dashboard
git pull --ff-only origin feature/streamlit-visual-dashboard
```

Abre una terminal con el entorno virtual activo:

```powershell
cd "MindTEC_Audit_Engine\MindTEC_Intelligence_Audit_System_v0.1 copy"
python -m streamlit run app.py --server.address 127.0.0.1
```

Visita `http://localhost:8501`. Si la app estaba ejecutándose, detenla primero con Ctrl+C y vuelve a iniciarla para aplicar la configuración de tema y red.

## Seguridad

El dashboard HTML y los archivos de trabajo pueden contener información privada de MindTEC, incluso si solo se muestran algunas tablas. **No** inicies este servidor en `0.0.0.0` ni uses el enlace Network URL con datos empresariales, sin autenticación y autorización de Sistemas. El tema local incluye `[server] address = "127.0.0.1"`; se recomienda usar también el parámetro explícito mostrado.

La vista HTML solo abre las dos rutas predefinidas. Los archivos deben ser generados o revisados por el operador: contienen JavaScript embebido y la aplicación los renderiza en un iframe. No aceptes HTML desconocido ni lo subas al repositorio público. No agregues untracked files mediante `git add .`.

## Verificaciones

```powershell
python -m unittest discover -s tests -p "test_visual_dashboard.py" -v
```

También se ejecuta un test automático mediante GitHub Actions al proponer cambios.

## Qué NO se ha implementado

- Actualización en vivo del HTML original a partir de una API.
- Conciliación automática completa de los 12 KPI oficiales.
- Aprobación histórica de pesos, reglas de SKU, aplicabilidad y universo.
- Autenticación, roles y despliegue multiusuario del servidor Streamlit.
- Sincronización del HTML estático con los resultados de sesión de Streamlit.

Estas actividades son una segunda etapa técnica y requieren fuentes autorizadas y definiciones de negocio aprobadas.
