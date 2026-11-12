from pathlib import Path
import re,json,zipfile,argparse
HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description='Build a local MindTEC HTML dashboard from private audit inputs.')
parser.add_argument('--data-dir',type=Path,required=True,help='Private audit workspace, never uploaded to GitHub')
parser.add_argument('--output-dir',type=Path,default=HERE/'dist')
args=parser.parse_args();p=args.data_dir.resolve();output=args.output_dir.resolve();output.mkdir(parents=True,exist_ok=True)
required=[p/'executive-data.json',p/'MindTEC_KPI_originales_restaurados.html',p/'Exportacion_KPI_disponibles_2026-11-12'/'resultados_12_KPI.json']
for f in required:
    if not f.is_file():parser.error('Missing private input: '+str(f))
s=(HERE/'executive-template.html').read_text(encoding='utf-8')
s=s.replace('<title>MindTEC · Informe ejecutivo de auditoría</title>','<title>MindTEC · Vista visual del dashboard</title>')
s=s.replace('</style>',(HERE/'visual.css').read_text(encoding='utf-8')+'</style>',1)
s=re.sub(r'<header>.*?</header>','<header><div><strong>Dashboard de auditoría comercial</strong><div class="muted">Marcas, distribuidores y trazabilidad de datos</div></div><small>Información recuperada · 12/11/2026<br>Datos del panel v330 · septiembre / octubre</small></header><aside class="visual-sidebar"><strong>Mind<em>TEC</em></strong><small>INTELLIGENCE & DATA AUDIT</small><a href="#resumen">Vista general</a><a href="#visual-indicators">Los 12 indicadores</a><a href="#indicadores">Comparación de marcas</a><a href="#documentos">Distribuidores</a><a href="#hallazgos">Hallazgos y evidencia</a><a href="#plan">Plan de cierre</a><a href="#metodo">Fuentes y métodos</a><div class="sidebar-note">VISTA DE PRESENTACIÓN<br>Datos reales recuperados.<br>Los cálculos pendientes conservan su estado.<br><br>Sin conexión en vivo.</div></aside>',s,count=1,flags=re.S)
s=re.sub(r'<section class="hero" id="resumen">.*?</section>','<section id="resumen" style="margin-top:0"><div class="visual-title"><div><span class="eyebrow">MAQUETA VISUAL CON DATOS REALES</span><h1>Auditoría comercial, a la vista</h1><p>12 KPI · 64 marcas con publicación · 25 distribuidores documentados</p></div><div><button class="primary" onclick="window.print()">Imprimir / PDF</button> <button id="export-all">Exportar datos</button></div></div><div class="visual-note">Vista inicial de ejemplo: <b>Coca-Cola · octubre · gaseosas</b>. Puedes elegir cualquier marca y mes. Las cifras publicadas, auditoras y operativas se mantienen separadas; los resultados no reconstruidos se identifican explícitamente.</div></section>',s,count=1,flags=re.S)
s=s.replace('<div id="stats" class="cards"></div>','<div id="stats" class="cards"></div><section id="visual-indicators"><div class="section-head"><div><span class="section-label">PANEL DE INDICADORES</span><h2>Los 12 KPI de la selección</h2></div><small>Valores y respaldo visibles, sin desplegar pestañas</small></div><div id="visual-kpis" class="visual-kpi-grid"></div></section>')
s=s.replace('<h2>Los 12 KPI · todas las marcas</h2>','<h2>Comparación visual de todas las marcas</h2>')
s=s.replace('<div id="chart"></div>','<p class="visual-intro">El gráfico compara todas las marcas de su categoría y mes. La marca superior controla las tarjetas de indicadores; aquí se mantiene la comparación de competidores.</p><div id="chart"></div>')
s=s.replace('<div class="card"><h3>Cobertura y requisitos de los 12 indicadores</h3>','<div class="card visual-matrix"><h3>Matriz publicada · todas las marcas y los 12 KPI</h3><div id="visual-matrix"></div></div><div class="card"><h3>Cobertura y requisitos de los 12 indicadores</h3>')
s=s.replace('Este HTML contiene resultados, fórmulas, controles documentales y fichas para consulta ejecutiva.','Esta maqueta visual contiene resultados reales, fórmulas, controles documentales y fichas para presentar y explorar el dashboard.')
d=json.loads((p/'executive-data.json').read_text(encoding='utf-8'))
original=(p/'MindTEC_KPI_originales_restaurados.html').read_text(encoding='utf-8')
base=json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>',original,re.S).group(1))
available=json.loads((p/'Exportacion_KPI_disponibles_2026-11-12'/'resultados_12_KPI.json').read_text(encoding='utf-8'))
needed={r['sourceGroup'] for r in d['results'] if r['sourceGroup']}
pairs=[];pair_ids={};groups=[]
for key in sorted(needed):
    rows=[]
    for entry in base['reconstructionSources'].get(key,[]):
        row={k:v for k,v in entry.items() if k!='fields'};row['pairs']=[]
        for field in entry['fields']:
            token=json.dumps(field,ensure_ascii=False)
            if token not in pair_ids:pair_ids[token]=len(pairs);pairs.append(field)
            row['pairs'].append(pair_ids[token])
        rows.append(row)
    groups.append({'key':key,'rows':rows})
d['trace']={'pairs':pairs,'groups':groups,'records':base['records'],'visits':base['visitas'],'invoices':base['currentAudit']['items'],'links':{r['id']:{'invoices':r['operativo']['lineas_factura_relacionadas'],'stores':r['operativo']['tiendas_relacionadas'],'faces':r['operativo']['registros_caras_relacionados']} for r in available}}
s=s.replace('<a href="#hallazgos">Hallazgos y evidencia</a>','<a href="#trazabilidad">Trazabilidad directa</a><a href="#hallazgos">Hallazgos y evidencia</a>')
s=s.replace('<a href="#hallazgos">Hallazgos</a>','<a href="#trazabilidad">Trazabilidad</a><a href="#hallazgos">Hallazgos</a>')
s=s.replace('<section id="hallazgos">','<section id="trazabilidad"><span class="section-label">DEL RESULTADO AL REGISTRO ORIGINAL</span><h2>Trazabilidad y reconstrucción</h2><div id="trace-reconstruction"></div><div class="card"><h3>Qué puede reconstruirse en esta selección</h3><p>Abre un KPI para recorrer fórmula, universo relacionado, variables y líneas de factura. La aplicabilidad oficial desconocida sigue identificada.</p><div class="filters"><label>Buscar KPI, tienda, sticker o ID<input id="trace-search" placeholder="Ej. 10000023 o Perfect Store"></label><button id="trace-export-inputs">Exportar universos y variables</button></div><div id="trace-ledger"></div></div><div class="card"><h3>Tiendas y variables de origen</h3><div id="trace-inputs"></div></div></section><section id="hallazgos">')
s=s.replace('Sin conexión en vivo.','Sin conexión en vivo.<br>Variables y facturas integradas.')
s=s.replace('<section id="trazabilidad">',(HERE/'statistics-section.html').read_text(encoding='utf-8')+'<section id="trazabilidad">',1)
s=s.replace('<a href="#trazabilidad">Trazabilidad directa</a>','<a href="#estadistica">Estadística y χ²</a><a href="#trazabilidad">Trazabilidad directa</a>')
s=s.replace('<a href="#trazabilidad">Trazabilidad</a>','<a href="#estadistica">Estadística</a><a href="#trazabilidad">Trazabilidad</a>')
s=s.replace('</style>',' .trace-flow{display:flex;flex-wrap:wrap;gap:8px;margin:18px 0}.trace-flow span{padding:8px 12px;background:#eef2f8;border:1px solid #dce4f0;border-radius:6px;font-size:12px}.trace-flow span:first-child{background:#20324e;color:white} #trazabilidad .cards{grid-template-columns:repeat(4,minmax(0,1fr))}@media(max-width:900px){#trazabilidad .cards{grid-template-columns:repeat(2,minmax(0,1fr))}} </style>',1)
s=s.replace('</style>','.period-delta-row{display:grid;grid-template-columns:140px minmax(0,1fr) 85px;gap:12px;align-items:center;margin:10px 0;font-size:12px}.period-delta-track{height:14px;position:relative;background:linear-gradient(to right,#edf1f8 49.8%,#8a98ae 49.8%,#8a98ae 50.2%,#edf1f8 50.2%);border-radius:3px}.period-delta-track i{position:absolute;top:2px;height:10px;border-radius:3px}#stats-trend{margin-top:22px}@media(max-width:600px){.period-delta-row{grid-template-columns:95px minmax(0,1fr) 65px}} </style>',1)
payload=json.dumps(d,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')
script=(HERE/'executive.js').read_text(encoding='utf-8')+'\n'+(HERE/'visual.js').read_text(encoding='utf-8')+'\n'+(HERE/'trace-visual.js').read_text(encoding='utf-8')
script+='\n'+(HERE/'statistics-core.js').read_text(encoding='utf-8')+'\n'+(HERE/'statistics-visual.js').read_text(encoding='utf-8')
script+='\n'+(HERE/'statistics-periods.js').read_text(encoding='utf-8')
s=s.replace('__DATA__',payload).replace('__SCRIPT__',script)
s=re.sub(r'<p><a href="MindTEC_Dashboard_informacion_recuperada_2026-11-12.html".*?</p>','<p>La trazabilidad directa se encuentra integrada en este mismo HTML.</p>',s,flags=re.S)
s=s.replace('El enlace requiere conservar ambos HTML en la misma carpeta, tal como vienen en el ZIP.','Los registros y filas de origen se consultan desde la sección Trazabilidad.')
out=output/'MindTEC_Dashboard_con_auditoria_y_trazabilidad.html';out.write_text(s,encoding='utf-8')
with zipfile.ZipFile(output/'MindTEC_Dashboard_privado.zip','w',zipfile.ZIP_DEFLATED) as z:z.write(out,out.name)
print(json.dumps({'archivo':str(out),'bytes':out.stat().st_size,'datos_publicados_en_GitHub':False},ensure_ascii=False))
