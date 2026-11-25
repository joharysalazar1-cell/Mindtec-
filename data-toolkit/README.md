# Bibliotecas de datos de MindTEC

51 bibliotecas directas en 10 perfiles instalables y un [catálogo de repositorios oficiales](BIBLIOTECAS.md). El catálogo guarda versión seleccionada, última versión consultada, requisito de Python, licencia declarada, procedencia y enlaces. No crea forks ni copia código de terceros: los repositorios de referencia quedan guardados como enlaces documentados dentro de Mindtec-.

## Elegir un perfil

| Perfil | Uso |
| --- | --- |
| core | Paquetes del motor existente: tablas, estadística, SQL, interfaz y gráficos |
| formats | Excel, Parquet, Arrow y JSON |
| quality | Contratos, calidad, faltantes y propuestas de normalización |
| connectors | HTTP, reintentos, configuración y bases relacionales |
| statistics | Comparaciones estadísticas y supervivencia |
| visualization | Gráficos complementarios y mapas |
| documents | PDF, Word, PowerPoint y plantillas |
| geo | Geometrías y sistemas de coordenadas |
| development | Pruebas, análisis estático, vulnerabilidades e inventario SBOM |
| notebooks | Jupyter, kernels y exportación |

## Instalar de forma aislada

Desde la raíz del repositorio, con Python 3.14 de 64 bits en Windows:

```powershell
python -m venv data-toolkit/.venv
data-toolkit/.venv/Scripts/python.exe -m pip install -r data-toolkit/requirements/core.txt -r data-toolkit/requirements/quality.txt
data-toolkit/.venv/Scripts/python.exe data-toolkit/check_environment.py core quality
```

Para instalar el conjunto completo reproducible en **Windows x64 / CPython 3.14**:

```powershell
data-toolkit/.venv/Scripts/python.exe -m pip install --require-hashes --only-binary=:all: -r data-toolkit/requirements/windows-py314.lock.txt
data-toolkit/.venv/Scripts/python.exe -m pip check
```

El lock incluye dependencias transitivas y hashes de los wheels seleccionados. Es específico de esa plataforma; no reutilizar en Linux, macOS u otra versión de Python. Los perfiles son pines directos: en otras plataformas resolver e inspeccionar un lock propio. La versión mínima conjunta por metadatos es Python 3.12; la resolución guardada corresponde únicamente a 3.14/Windows.

Para ejecutar el motor con este entorno:

```powershell
data-toolkit/.venv/Scripts/python.exe -m streamlit run "MindTEC_Audit_Engine/MindTEC_Intelligence_Audit_System_v0.1 copy/app.py"
```

Los requisitos históricos permanecen intactos: este toolkit es una ruta de entorno adicional. Instalar los paquetes no integra automáticamente sus funciones en el dashboard privado, cuyo runtime publicado es JavaScript.

## Compatibilidad y trazabilidad

Se fijó pandas 2.3.3 porque lifelines 0.30.3 declara pandas<3. `selection_reason` registra la decisión. Consultar [el resumen de resolución](resolution-summary.json) para conocer todas las versiones transitivas, hashes y entorno del resolver. Una resolución satisfactoria no equivale a haber ejecutado todos los algoritmos de todas las bibliotecas.

Actualizar exige revisar cambios y resolver otra vez:

```powershell
python data-toolkit/refresh_catalog.py
python -m pip install --dry-run --ignore-installed --only-binary=:all: --report data-toolkit/resolution-windows-py314.json -r data-toolkit/requirements/all.txt
python data-toolkit/freeze_resolution.py
python data-toolkit/test_catalog.py
```

El primer comando consulta PyPI y modifica pines y catálogo; no debe ejecutarse como actualización automática sin revisión. Ni el refresco ni el comprobador de entorno instalan paquetes por su cuenta.

## Auditoría de uso

Los hashes del lock verifican artefactos descargados; no certifican la exactitud de un análisis. Guardar junto a cada ejecución: versiones instaladas, hash del archivo original, reglas, filtros, denominadores y resultados. `hashlib`, `sqlite3`, `logging`, `decimal` y `zoneinfo` ya forman parte de Python y no requieren paquetes externos.

Los matches de RapidFuzz son propuestas que requieren revisión; no homologan marcas o distribuidores automáticamente. Extraer tablas de PDF tampoco valida su contenido. No subir bases reales, claves API, entornos virtuales ni salidas de análisis al repositorio público.

El perfil development permite generar un SBOM y consultar vulnerabilidades conocidas del entorno instalado. Su inclusión no implica que se haya completado una auditoría de seguridad. Las licencias declaradas están en el catálogo; algunas bibliotecas tienen obligaciones específicas de redistribución que deben revisarse según el uso.
