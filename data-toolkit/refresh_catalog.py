"""Refresh only declared data dependencies from official PyPI JSON metadata."""
from __future__ import annotations
import concurrent.futures, datetime, json, pathlib, re, urllib.request

ROOT=pathlib.Path(__file__).resolve().parent
VERSION_OVERRIDES={'pandas':('2.3.3','lifelines 0.30.3 requires pandas<3; preserve compatibility of the combined toolkit.')}
REPOSITORY_OVERRIDES={'openpyxl':'https://foss.heptapod.net/openpyxl/openpyxl','xlrd':'https://github.com/python-excel/xlrd','Unidecode':'https://github.com/avian2/unidecode','nbconvert':'https://github.com/jupyter/nbconvert'}
DECLARATIONS='''core|pandas|pandas|Tablas, limpieza y cruces
core|numpy|numpy|Cálculo numérico
core|openpyxl|openpyxl|Lectura y escritura XLSX
core|xlrd|xlrd|Lectura de Excel XLS heredado
core|streamlit|streamlit|Interfaz existente del motor Python
core|scipy|scipy|Estadística y optimización
core|statsmodels|statsmodels|Regresión e inferencia estadística
core|scikit-learn|sklearn|Modelos exploratorios y evaluación
core|duckdb|duckdb|SQL analítico local
core|plotly|plotly|Gráficos interactivos
core|matplotlib|matplotlib|Gráficos exportables
formats|pyarrow|pyarrow|Parquet y Arrow
formats|polars|polars|Procesamiento tabular y consultas diferidas
formats|xlsxwriter|xlsxwriter|Informes Excel con formato
formats|pyxlsb|pyxlsb|Lectura Excel binario
formats|python-calamine|python_calamine|Motor alternativo Excel
formats|orjson|orjson|Serialización JSON
formats|charset-normalizer|charset_normalizer|Detección de codificación de texto
quality|pandera[pandas]|pandera|Esquemas y controles de tablas
quality|pydantic|pydantic|Validación de contratos de entrada
quality|rapidfuzz|rapidfuzz|Propuestas de coincidencia de nombres
quality|Unidecode|unidecode|Normalización exploratoria de texto
quality|missingno|missingno|Visualización de faltantes
connectors|httpx|httpx|Clientes HTTP con límites y timeout
connectors|tenacity|tenacity|Reintentos controlados
connectors|python-dotenv|dotenv|Configuración local fuera de Git
connectors|SQLAlchemy|sqlalchemy|Acceso a bases relacionales
connectors|psycopg[binary]|psycopg|Conector PostgreSQL
connectors|fsspec|fsspec|Abstracción de archivos remotos
statistics|pingouin|pingouin|Pruebas y tamaños de efecto
statistics|lifelines|lifelines|Análisis de supervivencia
statistics|scikit-posthocs|scikit_posthocs|Comparaciones posteriores a pruebas
visualization|seaborn|seaborn|Gráficos estadísticos
visualization|altair|altair|Visualización declarativa
visualization|folium|folium|Mapas interactivos
documents|pypdf|pypdf|Lectura y manipulación PDF
documents|pdfplumber|pdfplumber|Extracción de tablas PDF
documents|python-docx|docx|Informes Word
documents|python-pptx|pptx|Presentaciones de resultados
documents|Jinja2|jinja2|Plantillas de informes
geo|geopandas|geopandas|Análisis geográfico
geo|shapely|shapely|Geometrías y operaciones espaciales
geo|pyproj|pyproj|Sistemas de coordenadas
development|pytest|pytest|Pruebas automatizadas
development|hypothesis|hypothesis|Pruebas basadas en propiedades
development|ruff|ruff|Análisis estático de Python
development|pip-audit|pip_audit|Consulta de vulnerabilidades conocidas
development|cyclonedx-bom|cyclonedx|Inventario SBOM del entorno
notebooks|jupyterlab|jupyterlab|Cuadernos de investigación
notebooks|ipykernel|ipykernel|Kernel Python para cuadernos
notebooks|nbconvert|nbconvert|Exportación de cuadernos
'''

def fetch(line):
    group,requirement,module,purpose=line.split('|')
    name=requirement.split('[')[0]
    request=urllib.request.Request(f'https://pypi.org/pypi/{name}/json',headers={'User-Agent':'MindTEC-library-catalog/1.0'})
    with urllib.request.urlopen(request,timeout=30) as response: data=json.load(response)
    latest=data['info']['version']
    if name in VERSION_OVERRIDES:
        version,_=VERSION_OVERRIDES[name]
        with urllib.request.urlopen(f'https://pypi.org/pypi/{name}/{version}/json',timeout=30) as response:data=json.load(response)
    info=data['info'];urls=info.get('project_urls') or {}
    ranked=sorted(urls.items(),key=lambda kv: (0 if re.search('source|repository|code',kv[0],re.I) else 1,kv[0]))
    repo=next((u.rstrip('/') for _,u in ranked if 'github.com/' in u and not any(x in u for x in ['/issues','/discussions','/actions'])),None)
    repo=REPOSITORY_OVERRIDES.get(name,repo)
    declared_license=info.get('license_expression') or info.get('license') or 'Consultar distribución'
    if len(declared_license)>300:declared_license=declared_license[:300]+'… (texto completo en metadata_api)'
    return dict(group=group,name=info['name'],requirement=requirement,version=info['version'],latest_version=latest,selection_reason=VERSION_OVERRIDES.get(name,('', 'Latest release at metadata refresh'))[1],module=module,purpose=purpose,requires_python=info.get('requires_python'),license=declared_license,repository=repo,repository_source='Official project docs / repository' if name in REPOSITORY_OVERRIDES else 'PyPI project metadata',project_urls=urls,pypi=f'https://pypi.org/project/{info["name"]}/{info["version"]}/',metadata_api=f'https://pypi.org/pypi/{name}/{info["version"]}/json')

def main():
    rows=DECLARATIONS.strip().splitlines()
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool: packages=list(pool.map(fetch,rows))
    checked=datetime.datetime.now(datetime.timezone.utc).isoformat()
    (ROOT/'catalog.json').write_text(json.dumps({'checked_at_utc':checked,'source':'PyPI project metadata; versions are direct pins, not a resolved environment','packages':packages},ensure_ascii=False,indent=2),encoding='utf-8')
    req=ROOT/'requirements';req.mkdir(exist_ok=True)
    groups=list(dict.fromkeys(x['group'] for x in packages))
    for group in groups:
        content='# Direct pins from PyPI; see ../catalog.json.\n'+''.join(f'{x["requirement"]}=={x["version"]}\n' for x in packages if x['group']==group)
        (req/f'{group}.txt').write_text(content,encoding='utf-8')
    (req/'all.txt').write_text('# Optional full toolkit; resolve in an isolated environment first.\n'+''.join(f'-r {g}.txt\n' for g in groups),encoding='utf-8')
    md=['# Bibliotecas y repositorios oficiales de datos','',f'Metadatos consultados: {checked}. Enlaces obtenidos de PyPI y documentación oficial; catalog.json registra la procedencia de cada repositorio. Las versiones son pines directos; la compatibilidad del entorno se registra por separado.','']
    for group in groups:
        md += [f'## {group}','', '| Paquete | Versión | Uso | Código oficial | Distribución |','| --- | --- | --- | --- | --- |']
        for x in packages:
            if x['group']==group:
                link=f'[Repositorio]({x["repository"]})' if x['repository'] else 'Ver enlaces de distribución'
                md.append(f'| {x["name"]} | {x["version"]} | {x["purpose"]} | {link} | [PyPI]({x["pypi"]}) |')
        md.append('')
    (ROOT/'BIBLIOTECAS.md').write_text('\n'.join(md),encoding='utf-8')
    print(json.dumps({'packages':len(packages),'profiles':groups,'repositories':sum(bool(p['repository']) for p in packages)}))

if __name__=='__main__':main()
