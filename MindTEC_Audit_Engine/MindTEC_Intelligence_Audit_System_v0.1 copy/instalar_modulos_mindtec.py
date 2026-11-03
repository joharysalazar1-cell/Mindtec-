# MindTEC: instalador de módulos. Ejecutar desde la carpeta del proyecto.
from pathlib import Path
from datetime import datetime
import sys

FILES = {'app.py': 'import importlib.util\n'
           'from pathlib import Path\n'
           'import streamlit as st\n'
           '\n'
           "st.set_page_config(page_title='MindTEC Intelligence System',page_icon='📊',layout='wide')\n"
           'ROOT=Path(__file__).resolve().parent\n'
           'PAGES={\n'
           "    'Recepción de datos':('01_data_upload.py','pagina_recepcion_datos'),\n"
           "    'Explorador de datos':('02_data_explorer.py','render'),\n"
           "    'Modelo de datos':('03_data_model.py','render'),\n"
           "    'Análisis descriptivo':('04_descriptive_analysis.py','render'),\n"
           "    'Tablas cruzadas':('05_crosstabs.py','render'),\n"
           "    'Inteligencia comercial':('06_market_intelligence.py','render'),\n"
           "    'Modelos estadísticos':('07_statistical_models.py','render'),\n"
           "    'Resultados':('08_results.py','render'),\n"
           '}\n'
           '\n'
           'def load_page(filename):\n'
           "    path=ROOT/'interface'/'pages'/filename\n"
           "    spec=importlib.util.spec_from_file_location('mindtec_'+filename.replace('.','_'),path)\n"
           '    module=importlib.util.module_from_spec(spec)\n'
           '    spec.loader.exec_module(module)\n'
           '    return module\n'
           '\n'
           "st.sidebar.title('📊 MindTEC')\n"
           "choice=st.sidebar.radio('Navegación',['Inicio']+list(PAGES))\n"
           "if choice=='Inicio':\n"
           "    st.title('MindTEC Intelligence System')\n"
           "    st.caption('Plataforma de investigación de mercados e inteligencia comercial · versión "
           "funcional inicial')\n"
           "    st.info('Comienza en Recepción de datos. Las fuentes se conservan en memoria durante la "
           "sesión y no se modifican.')\n"
           "    st.write('Módulos disponibles:',len(PAGES))\n"
           "    st.warning('La validez de cada análisis depende de la unidad de observación, calidad, "
           "cobertura y diseño muestral. Las 12 aristas requieren fuentes apropiadas.')\n"
           'else:\n'
           '    filename,method=PAGES[choice]\n'
           '    try:\n'
           '        getattr(load_page(filename),method)()\n'
           '    except Exception as exc:\n'
           "        st.error(f'Error en el módulo «{choice}»: {exc}')\n"
           '        st.exception(exc)\n',
 'interface/pages/02_data_explorer.py': 'import streamlit as st\n'
                                        'import pandas as pd\n'
                                        'from src.services.workspace import select_data, csv_button\n'
                                        '\n'
                                        'def render():\n'
                                        "    st.title('🔎 Explorador de datos')\n"
                                        "    df, _ = select_data(key='explore')\n"
                                        '    if df is None: return\n'
                                        '    a,b,c = st.columns(3)\n'
                                        "    a.metric('Registros',len(df)); "
                                        "b.metric('Variables',len(df.columns)); c.metric('Celdas "
                                        "vacías',int(df.isna().sum().sum()))\n"
                                        "    selected = st.multiselect('Columnas visibles', "
                                        'list(df.columns), default=list(df.columns))\n'
                                        '    if not selected: return\n'
                                        '    filtered = df[selected].copy()\n'
                                        "    filter_col = st.selectbox('Filtrar por variable (opcional)', "
                                        "['(sin filtro)']+selected)\n"
                                        "    if filter_col != '(sin filtro)':\n"
                                        '        vals = '
                                        'filtered[filter_col].dropna().astype(str).unique().tolist()\n'
                                        '        if len(vals) <= 1000:\n'
                                        "            chosen = st.multiselect('Valores permitidos', "
                                        'sorted(vals), default=[])\n'
                                        '            if chosen: filtered = '
                                        'filtered[filtered[filter_col].astype(str).isin(chosen)]\n'
                                        '        else:\n'
                                        "            st.warning('Demasiados valores únicos para el selector; "
                                        "el filtro se omite.')\n"
                                        '    st.dataframe(filtered.head(1000), use_container_width=True)\n'
                                        "    st.caption('Vista limitada a 1.000 filas; la exportación "
                                        "incluye todas las filas filtradas.')\n"
                                        '    profile = '
                                        "pd.DataFrame({'variable':df.columns,'tipo':df.dtypes.astype(str).values,'no_nulos':df.notna().sum().values,'nulos':df.isna().sum().values,'unicos':df.nunique(dropna=True).values})\n"
                                        "    st.subheader('Perfil de variables'); st.dataframe(profile, "
                                        'use_container_width=True, hide_index=True)\n'
                                        "    csv_button(filtered, 'exploracion.csv')\n",
 'interface/pages/03_data_model.py': 'import streamlit as st\n'
                                     'import pandas as pd\n'
                                     'from src.services.workspace import sources, get_df\n'
                                     '\n'
                                     'def render():\n'
                                     "    st.title('🧩 Modelo de datos')\n"
                                     '    data = sources()\n'
                                     '    if not data:\n'
                                     "        st.info('Carga al menos un archivo.'); return\n"
                                     '    rows=[]\n'
                                     '    for k,r in data.items():\n'
                                     '        try:\n'
                                     '            df=get_df(k)\n'
                                     '            '
                                     "rows.append({'fuente':r['nombre'],'id':k[:10],'filas':len(df),'columnas':len(df.columns),'variables':', "
                                     "'.join(map(str,df.columns))})\n"
                                     '        except Exception as e: '
                                     "rows.append({'fuente':r['nombre'],'error':str(e)})\n"
                                     '    '
                                     'st.dataframe(pd.DataFrame(rows),use_container_width=True,hide_index=True)\n'
                                     "    st.warning('No se combinan tablas automáticamente. Una "
                                     "coincidencia de nombre no demuestra una relación válida.')\n"
                                     '    if len(data)<2: return\n'
                                     '    keys=list(data)\n'
                                     "    left=st.selectbox('Tabla izquierda',keys,format_func=lambda "
                                     "k:data[k]['nombre']+' · '+k[:8],key='model_left')\n"
                                     "    right=st.selectbox('Tabla derecha',keys,index=1,format_func=lambda "
                                     "k:data[k]['nombre']+' · '+k[:8],key='model_right')\n"
                                     '    if left==right:\n'
                                     "        st.info('Elige dos fuentes diferentes.'); return\n"
                                     '    try:\n'
                                     '        a,b=get_df(left),get_df(right)\n'
                                     "        lc=st.selectbox('Clave izquierda',list(a.columns)); "
                                     "rc=st.selectbox('Clave derecha',list(b.columns))\n"
                                     '        al=a[lc].dropna(); bl=b[rc].dropna()\n'
                                     '        x,y,z=st.columns(3)\n'
                                     "        x.metric('Duplicados clave "
                                     "izquierda',int(al.duplicated().sum()))\n"
                                     "        y.metric('Duplicados clave "
                                     "derecha',int(bl.duplicated().sum()))\n"
                                     "        z.metric('Nulos en ambas "
                                     "claves',int(a[lc].isna().sum()+b[rc].isna().sum()))\n"
                                     "        st.write('Coincidencias entre claves (comparación textual, sin "
                                     "alterar las fuentes):',len(set(al.astype(str)) & "
                                     'set(bl.astype(str))))\n'
                                     "        st.caption('Esto es diagnóstico, no una unión. Revisa "
                                     'granularidad, tipos, identificadores y cardinalidad antes de definir '
                                     "relaciones.')\n"
                                     '    except Exception as e: st.error(str(e))\n',
 'interface/pages/04_descriptive_analysis.py': 'import streamlit as st\n'
                                               'import pandas as pd\n'
                                               'import plotly.express as px\n'
                                               'from src.services.workspace import select_data,csv_button\n'
                                               '\n'
                                               'def render():\n'
                                               "    st.title('📐 Análisis descriptivo')\n"
                                               "    df,_=select_data(key='desc')\n"
                                               '    if df is None:return\n'
                                               '    '
                                               "col=st.selectbox('Variable',list(df.columns),key='desc_col')\n"
                                               "    s=df[col]; st.write('Valores "
                                               "válidos:',int(s.notna().sum()),' · "
                                               "Faltantes:',int(s.isna().sum()))\n"
                                               '    if pd.api.types.is_numeric_dtype(s):\n'
                                               '        '
                                               "desc=s.describe().rename_axis('estadístico').reset_index(name='valor')\n"
                                               '        '
                                               'st.dataframe(desc,use_container_width=True,hide_index=True)\n'
                                               '        '
                                               "st.plotly_chart(px.histogram(df,x=col,title='Distribución'),use_container_width=True)\n"
                                               "        csv_button(desc,'estadisticos.csv')\n"
                                               '    else:\n'
                                               "        counts=s.fillna('(sin "
                                               "dato)').astype(str).value_counts(dropna=False).rename_axis('categoria').reset_index(name='frecuencia')\n"
                                               '        '
                                               "counts['porcentaje']=counts['frecuencia']/len(s)*100\n"
                                               '        '
                                               'st.dataframe(counts,use_container_width=True,hide_index=True)\n'
                                               '        '
                                               "st.plotly_chart(px.bar(counts.head(30),x='categoria',y='frecuencia',title='Frecuencias "
                                               "(hasta 30 categorías)'),use_container_width=True)\n"
                                               "        csv_button(counts,'frecuencias.csv')\n",
 'interface/pages/05_crosstabs.py': 'import streamlit as st\n'
                                    'import pandas as pd\n'
                                    'from scipy.stats import chi2_contingency\n'
                                    'from src.services.workspace import select_data,csv_button\n'
                                    '\n'
                                    'def render():\n'
                                    "    st.title('🔀 Tablas cruzadas')\n"
                                    "    df,_=select_data(key='cross')\n"
                                    '    if df is None:return\n'
                                    "    if len(df.columns)<2: st.info('Se requieren dos "
                                    "variables.');return\n"
                                    "    a=st.selectbox('Variable de filas',list(df.columns),key='cross_a')\n"
                                    "    b=st.selectbox('Variable de "
                                    "columnas',list(df.columns),index=1,key='cross_b')\n"
                                    "    if a==b: st.warning('Selecciona variables distintas.');return\n"
                                    "    mode=st.radio('Mostrar',['Frecuencias','% por fila','% por "
                                    "columna','% del total'],horizontal=True)\n"
                                    '    valid=df[[a,b]].dropna()\n'
                                    "    if valid.empty: st.warning('No hay pares válidos.');return\n"
                                    '    counts=pd.crosstab(valid[a],valid[b]); '
                                    'total=counts.to_numpy().sum()\n'
                                    "    if counts.empty: st.warning('No hay categorías.');return\n"
                                    "    if mode=='% por fila': "
                                    'out=counts.div(counts.sum(axis=1),axis=0)*100\n'
                                    "    elif mode=='% por "
                                    "columna':out=counts.div(counts.sum(axis=0),axis=1)*100\n"
                                    "    elif mode=='% del total':out=counts/total*100\n"
                                    '    else:out=counts\n'
                                    '    st.dataframe(out,use_container_width=True)\n'
                                    "    st.caption(f'N pares completos = {len(valid)}. Los faltantes se "
                                    "excluyen; los porcentajes no son ponderados.')\n"
                                    "    csv_button(out.reset_index(),'tabla_cruzada.csv')\n"
                                    '    if counts.shape[0]>1 and counts.shape[1]>1:\n'
                                    "        if counts.size>10000: st.info('Tabla demasiado grande para "
                                    "calcular chi-cuadrado automáticamente.');return\n"
                                    '        try:\n'
                                    '            '
                                    'chi,p,dof,expected=chi2_contingency(counts,correction=False)\n'
                                    "            st.subheader('Chi-cuadrado de independencia "
                                    "(exploratorio)')\n"
                                    "            st.write(f'χ² = {chi:.4f} · gl = {dof} · p = {p:.5g}')\n"
                                    "            if (expected<5).any():st.warning(f'{(expected<5).sum()} "
                                    'celdas con frecuencia esperada < 5: la aproximación asintótica puede '
                                    "ser poco fiable.')\n"
                                    "            st.caption('La inferencia requiere revisar diseño muestral, "
                                    'independencia de observaciones y ponderaciones. No implica '
                                    "causalidad.')\n"
                                    "        except ValueError as e:st.warning(f'Prueba no calculable: "
                                    "{e}')\n",
 'interface/pages/06_market_intelligence.py': 'import streamlit as st\n'
                                              'import pandas as pd\n'
                                              'import plotly.express as px\n'
                                              'from src.services.workspace import select_data,csv_button\n'
                                              '\n'
                                              "AREAS=['Distribución y cobertura','Disponibilidad y "
                                              "quiebres','Inventario y stock','Precios','Competencia y "
                                              "participación','Cadencia temporal','Portafolio y "
                                              "surtido','Rendimiento comercial (Sell-in)','Calidad y "
                                              "confiabilidad','Metodología','Predicción y "
                                              "modelos','Predicción operativa tienda-producto']\n"
                                              '\n'
                                              'def render():\n'
                                              "    st.title('🏪 Inteligencia comercial')\n"
                                              "    st.caption('Las 12 aristas son preguntas de "
                                              "investigación, no indicadores calculables automáticamente.')\n"
                                              "    area=st.selectbox('Arista de investigación',AREAS)\n"
                                              "    df,_=select_data(key='intel')\n"
                                              '    if df is None:return\n'
                                              "    st.info('Selecciona las variables que representan el "
                                              "fenómeno. No se infiere su significado por el nombre.')\n"
                                              "    if area=='Calidad y confiabilidad':\n"
                                              '        '
                                              "quality=pd.DataFrame({'variable':df.columns,'nulos':df.isna().sum().values,'porcentaje_nulos':(df.isna().mean()*100).round(2).values,'unicos':df.nunique().values})\n"
                                              '        '
                                              'st.dataframe(quality,use_container_width=True,hide_index=True)\n'
                                              "        st.metric('Filas exactamente "
                                              "duplicadas',int(df.duplicated().sum()))\n"
                                              "        csv_button(quality,'calidad.csv');return\n"
                                              "    if area=='Metodología':\n"
                                              "        st.write('Registros:',len(df),' · "
                                              "Variables:',len(df.columns))\n"
                                              "        st.warning('Para inferencia poblacional se requieren "
                                              'diseño de muestra, marco, unidades, conglomerados y factores '
                                              "de expansión cuando correspondan.')\n"
                                              '        return\n'
                                              "    if area in ('Predicción y modelos','Predicción operativa "
                                              "tienda-producto'):\n"
                                              "        st.info('Los modelos predictivos se configuran en "
                                              'Modelos estadísticos. Debe verificarse la unidad de '
                                              "observación y disponibilidad de variable objetivo.')\n"
                                              '        return\n'
                                              "    group=st.selectbox('Dimensión / "
                                              "categoría',list(df.columns),key='intel_group')\n"
                                              "    numeric=list(df.select_dtypes(include='number').columns)\n"
                                              "    measure=st.selectbox('Medida', ['Conteo de "
                                              "registros']+numeric,key='intel_measure')\n"
                                              "    if measure=='Conteo de registros':\n"
                                              '        '
                                              "result=df.groupby(group,dropna=False).size().reset_index(name='conteo')\n"
                                              "        val='conteo'\n"
                                              '    else:\n'
                                              '        '
                                              "op=st.selectbox('Agregación',['suma','promedio','mediana'],key='intel_agg')\n"
                                              '        '
                                              "fn={'suma':'sum','promedio':'mean','mediana':'median'}[op]\n"
                                              '        '
                                              'result=df.groupby(group,dropna=False)[measure].agg(fn).reset_index(name=measure)\n'
                                              '        val=measure\n'
                                              '    result=result.sort_values(val,ascending=False)\n'
                                              '    '
                                              'st.dataframe(result,use_container_width=True,hide_index=True)\n'
                                              '    '
                                              'st.plotly_chart(px.bar(result.head(30),x=group,y=val,title=area),use_container_width=True)\n'
                                              "    csv_button(result,'inteligencia_comercial.csv')\n"
                                              "    st.warning('Este cálculo es una agregación exploratoria. "
                                              'No equivale automáticamente a cobertura, cuota de mercado, '
                                              'quiebre, inventario o Sell-in; verifica la definición, '
                                              "denominador y granularidad.')\n",
 'interface/pages/07_statistical_models.py': 'import streamlit as st\n'
                                             'import pandas as pd\n'
                                             'import numpy as np\n'
                                             'import plotly.express as px\n'
                                             'from scipy import stats\n'
                                             'from src.services.workspace import select_data,csv_button\n'
                                             '\n'
                                             'def render():\n'
                                             "    st.title('📊 Modelos estadísticos')\n"
                                             "    df,_=select_data(key='stats')\n"
                                             '    if df is None:return\n'
                                             "    nums=list(df.select_dtypes(include='number').columns)\n"
                                             "    test=st.selectbox('Procedimiento',['Correlación "
                                             "Pearson/Spearman','Regresión lineal exploratoria'])\n"
                                             "    if len(nums)<2:st.info('Se necesitan al menos dos "
                                             "variables numéricas.');return\n"
                                             "    x=st.selectbox('Variable explicativa "
                                             "X',nums,key='stat_x')\n"
                                             "    y=st.selectbox('Variable respuesta "
                                             "Y',nums,index=1,key='stat_y')\n"
                                             "    if x==y:st.warning('Selecciona variables "
                                             "diferentes.');return\n"
                                             '    dat=df[[x,y]].replace([np.inf,-np.inf],np.nan).dropna()\n'
                                             "    if len(dat)<3:st.warning('Menos de tres pares "
                                             "válidos.');return\n"
                                             "    if dat[x].nunique()<2 or dat[y].nunique()<2:st.warning('Se "
                                             "requiere variación en ambas variables.');return\n"
                                             "    if test.startswith('Correlación'):\n"
                                             '        pearson=stats.pearsonr(dat[x],dat[y]); '
                                             'spearman=stats.spearmanr(dat[x],dat[y])\n'
                                             "        st.write(f'Pearson r = {pearson.statistic:.4f} · p = "
                                             "{pearson.pvalue:.5g}')\n"
                                             "        st.write(f'Spearman ρ = {spearman.statistic:.4f} · p = "
                                             "{spearman.pvalue:.5g}')\n"
                                             '    else:\n'
                                             '        import statsmodels.api as sm\n'
                                             '        model=sm.OLS(dat[y],sm.add_constant(dat[x])).fit()\n'
                                             "        st.write(f'Coeficiente X = {model.params.iloc[1]:.5g} "
                                             '· p = {model.pvalues.iloc[1]:.5g} · R² = '
                                             "{model.rsquared:.4f}')\n"
                                             "        with st.expander('Resumen del modelo'):\n"
                                             '            st.text(model.summary().as_text())\n'
                                             "        st.warning('Regresión exploratoria sin ajuste por "
                                             'confusores ni diagnóstico completo de supuestos. No es un '
                                             "pronóstico validado ni prueba causal.')\n"
                                             "    st.plotly_chart(px.scatter(dat,x=x,y=y,title=f'{x} frente "
                                             "a {y}'),use_container_width=True)\n"
                                             "    st.caption(f'N pares completos = {len(dat)}. Verifica "
                                             'independencia, muestreo y supuestos antes de interpretar '
                                             "valores p.')\n",
 'interface/pages/08_results.py': 'import streamlit as st\n'
                                  'import pandas as pd\n'
                                  'from src.services.workspace import sources,get_df,csv_button\n'
                                  '\n'
                                  'def render():\n'
                                  "    st.title('📦 Resultados y exportaciones')\n"
                                  "    st.caption('Los resultados se exportan desde cada módulo; aquí se "
                                  "muestra el inventario de fuentes de la sesión.')\n"
                                  '    data=sources()\n'
                                  "    if not data:st.info('Todavía no hay fuentes cargadas.');return\n"
                                  '    rows=[]\n'
                                  '    for k,r in data.items():\n'
                                  '        try:\n'
                                  '            df=get_df(k)\n'
                                  '            '
                                  "rows.append({'fuente':r['nombre'],'id_sha256':k,'registros':len(df),'variables':len(df.columns),'tamano_bytes':r['tamano']})\n"
                                  '        except Exception as '
                                  "e:rows.append({'fuente':r['nombre'],'error':str(e)})\n"
                                  '    result=pd.DataFrame(rows)\n'
                                  '    st.dataframe(result,use_container_width=True,hide_index=True)\n'
                                  "    csv_button(result,'inventario_fuentes.csv')\n"
                                  "    st.warning('No se han generado informes automáticos ni se han "
                                  "alterado las fuentes originales.')\n",
 'src/services/workspace.py': 'import io\n'
                              'import pandas as pd\n'
                              'import streamlit as st\n'
                              '\n'
                              '\n'
                              'def sources():\n'
                              "    return st.session_state.get('archivos_cargados', {})\n"
                              '\n'
                              '\n'
                              'def get_df(key, sheet=None):\n'
                              '    r = sources()[key]\n'
                              "    raw = io.BytesIO(r['contenido'])\n"
                              "    if r['extension'].lower() == 'csv':\n"
                              "        for enc in ('utf-8-sig', 'utf-8', 'cp1252', 'latin-1'):\n"
                              '            try:\n'
                              '                raw.seek(0)\n'
                              "                return pd.read_csv(raw, sep=None, engine='python', "
                              'encoding=enc)\n'
                              '            except UnicodeDecodeError:\n'
                              '                continue\n'
                              "        raise ValueError('No se pudo decodificar el CSV.')\n"
                              '    return pd.read_excel(raw, sheet_name=sheet or 0)\n'
                              '\n'
                              '\n'
                              "def select_data(label='Fuente de datos', key='source'):\n"
                              '    data = sources()\n'
                              '    if not data:\n'
                              "        st.info('Primero carga archivos en Recepción de datos.')\n"
                              '        return None, None\n'
                              '    ids = list(data)\n'
                              "    choice = st.selectbox(label, ids, format_func=lambda i: data[i]['nombre'] "
                              "+ ' · ' + i[:8], key=key)\n"
                              '    record = data[choice]\n'
                              '    sheet = None\n'
                              "    if record.get('hojas'):\n"
                              "        sheet = st.selectbox('Hoja de Excel', record['hojas'], "
                              "key=key+'_sheet')\n"
                              '    try:\n'
                              '        df = get_df(choice, sheet)\n'
                              '        if df.empty or not len(df.columns):\n'
                              "            st.warning('Esta fuente no contiene registros analizables.')\n"
                              '            return None, None\n'
                              '        return df, choice\n'
                              '    except Exception as exc:\n'
                              "        st.error(f'No se pudo leer la fuente: {exc}')\n"
                              '        return None, None\n'
                              '\n'
                              '\n'
                              "def csv_button(df, name='resultados.csv'):\n"
                              "    st.download_button('⬇ Exportar CSV', "
                              "df.to_csv(index=False).encode('utf-8-sig'), name, 'text/csv')\n"
                              '\n'
                              '\n'
                              'def variables(df, numeric=False):\n'
                              '    if numeric:\n'
                              "        return list(df.select_dtypes(include='number').columns)\n"
                              '    return list(df.columns)\n'}

root = Path.cwd()
if not (root / 'app.py').is_file() or not (root / 'interface' / 'pages' / '01_data_upload.py').is_file():
    sys.exit('ERROR: ejecuta este script en la carpeta que contiene app.py e interface/pages/01_data_upload.py')
backup = root / ('app_backup_' + datetime.now().strftime('%Y%m%d_%H%M%S') + '.py')
backup.write_bytes((root / 'app.py').read_bytes())
for name, content in FILES.items():
    dest = root / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and name != 'app.py':
        print('AVISO: reemplazando', name)
    dest.write_text(content, encoding='utf-8')
print('Instalación completa. Copia de app.py:', backup.name)
print('No se modificó 01_data_upload.py ni ningún archivo de datos.')
print('Ejecuta: streamlit run app.py')
