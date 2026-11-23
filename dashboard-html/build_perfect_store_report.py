from pathlib import Path
import argparse,json, zipfile
HERE=Path(__file__).resolve().parent
parser=argparse.ArgumentParser(description='Build a private Perfect Store report from prepared reconstruction JSON.')
parser.add_argument('--data-dir',type=Path,default=HERE)
parser.add_argument('--cut-id',default='2026-11-13',help='Corte YYYY-MM-DD que corresponde a la reconstrucción')
args=parser.parse_args()
from datetime import date
try:cut_id=date.fromisoformat(args.cut_id).isoformat()
except ValueError:parser.error('--cut-id debe usar una fecha YYYY-MM-DD válida')
p=args.data_dir.resolve()
o=p/f'Perfect_Store_reconstruido_{cut_id}'
def read(n): return json.loads((o/n).read_text(encoding='utf-8'))
details=read('detalle_por_tienda.json');fields=[];fi={};reasons=[];ri={};rows=[]
for row in details:
    r={k:v for k,v in row.items() if k!='componentes'};r['c']=[]
    for c in row['componentes']:
        reason=c['motivo']
        if reason not in ri:ri[reason]=len(reasons);reasons.append(reason)
        ids=[]
        for f in c['fuentes']:
            key=json.dumps(f,ensure_ascii=False)
            if key not in fi:fi[key]=len(fields);fields.append(f)
            ids.append(fi[key])
        r['c'].append(dict(n=c['componente'],s=c['estado'],v=c['valor'],r=ri[reason],f=ids))
    rows.append(r)
data=dict(rows=rows,fields=fields,reasons=reasons,summary=read('resumen_por_marca_mes.json'),manifest=read('manifiesto.json'),exclusions=read('reglas_y_fuentes.json')['exclusiones'],names=['Presencia','SKU núcleo','Frío','POP','Sin quiebre'])
payload=json.dumps(data,ensure_ascii=False,separators=(',',':')).replace('<','\u003c')
s=(HERE/'perfect-store-report.html').read_text(encoding='utf-8').replace('__DATA__',payload).replace('__SCRIPT__',(HERE/'perfect-store-report.js').read_text(encoding='utf-8')).replace('<script src="data:,"></script>','')
dest=o/'MindTEC_Perfect_Store_reconstruido.html';dest.write_text(s,encoding='utf-8')
# Add a reversible entry to the prior dashboard without mixing cohorts or
# overwriting its historical audit values with this newer operational cut.
dash=p/'MindTEC_Dashboard_con_auditoria_y_trazabilidad.html'
if dash.exists():
    h=dash.read_text(encoding='utf-8')
    start='<!-- PERFECT_STORE_'+cut_id.replace('-','_')+' -->';end='<!-- END_PERFECT_STORE_'+cut_id.replace('-','_')+' -->'
    import re
    h=re.sub(re.escape(start)+'.*?'+re.escape(end),'',h,flags=re.S)
    banner=start+'<aside style="margin:20px;padding:20px;border:1px solid #c9d7e8;background:#edf4ff;border-radius:10px"><b>Perfect Store reconstruido · corte '+cut_id+'</b><p>Respuestas originales, componentes por tienda, fórmulas y contraste con el panel. El corte operativo nuevo se consulta por separado de la auditoría histórica de esta página.</p><a href="Perfect_Store_reconstruido_'+cut_id+'/MindTEC_Perfect_Store_reconstruido.html">Abrir Perfect Store y su trazabilidad</a></aside>'+end
    h=re.sub(r'(<body[^>]*>)',lambda m:m[1]+banner,h,count=1)
    dash.write_text(h,encoding='utf-8')
with zipfile.ZipFile(p/f'MindTEC_Perfect_Store_reconstruido_{cut_id}.zip','w',zipfile.ZIP_DEFLATED) as z:
    for f in o.iterdir():
        if f.is_file(): z.write(f,o.name+'/'+f.name)
print(json.dumps(dict(html=str(dest),bytes=dest.stat().st_size,fields=len(fields),rows=len(rows)),ensure_ascii=False))
