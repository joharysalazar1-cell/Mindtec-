"""Render a verified export-coverage annex without treating absence as zero sales."""
import argparse,html,json
from pathlib import Path
import engine,collection_watch,report

def export(runtime,output,run_id=None):
 runtime=Path(runtime).resolve();output=Path(output).resolve()
 if output.is_relative_to(runtime):raise ValueError('Report must remain outside custody')
 if not (runtime/'audit.sqlite').is_file():raise ValueError('Existing impact custody required')
 with engine.Engine(runtime) as e:
  e.db.execute('BEGIN')
  try:
   head=e.verify();run=e.db.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone() if run_id else e.db.execute("SELECT * FROM runs WHERE json_extract(rules_json,'$.kind')='collection_export_impact' ORDER BY at DESC,id DESC LIMIT 1").fetchone()
   if not run:raise ValueError('Impact result unavailable')
   rules=engine.load_json_bytes(run['rules_json'].encode());result=engine.load_json_bytes(collection_watch.object_bytes(e,run['snapshot_hash']));findings=engine.load_json_bytes(run['findings_json'].encode());refs=rules['reference_sources']
   if rules.get('kind')!='collection_export_impact' or result['current_source_sha256']!=refs['current_workbook'] or result['previous_source_sha256']!=refs['reference_workbook']:raise ValueError('Impact sources differ from retained result')
   if [f['evidence'] for f in findings]!=result['presence_changes']:raise ValueError('Impact findings differ from retained rows')
   for digest in [refs['current_workbook'],refs['reference_workbook']]:
    report.collection_evidence(e,{'reference_sources':{'current_workbook':digest}},[f for f in findings if f['evidence']['source_sha256']==digest])
  finally:e.db.execute('ROLLBACK')
 E=lambda v:html.escape(str(v if v is not None else 'Vacío (null)'),quote=True)
 changes=result['presence_changes'];shelf=sum(g['measures']['Caras en góndola']['registered_subtotal_delta'] for g in result['category_subtotals']);cold=sum(g['measures']['Caras en frío']['registered_subtotal_delta'] for g in result['category_subtotals'])
 def table(heads,rows):return '<div class="scroll"><table><thead><tr>'+''.join('<th>'+E(h)+'</th>' for h in heads)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+c+'</td>' for c in row)+'</tr>' for row in rows)+'</tbody></table></div>'
 groups=[]
 for g in result['category_subtotals']:
  values=[]
  for field in ['Caras en góndola','Caras en frío']:
   m=g['measures'][field];a=m['previous'];b=m['current'];values.append(E(a['registered_subtotal'])+' → '+E(b['registered_subtotal'])+'<br><b>Δ '+E(m['registered_subtotal_delta'])+'</b><br><small>Filas sin medida inequívoca: '+E(a['missing_or_ambiguous_rows'])+' → '+E(b['missing_or_ambiguous_rows'])+'</small>')
  groups.append([E(g['month']),E(g['category']),E(g['previous_rows'])+' → '+E(g['current_rows']),*values])
 detail=[]
 for f in findings:
  c=f['evidence'];cells=table(['Celda original','Campo','Valor conservado'],[[E(r['sheet'])+'!'+E(r['coordinate']),E(r['column']),E(r['value'])] for r in c['cells']]);detail.append([E(c['brand'])+'<br><small>'+E(c['category'])+'</small>',E(c['internal_id'])+' / '+E(c['kobo_id']),E(c['month']),'Solo en el archivo anterior' if c['state']=='only_previous_export' else 'Solo en el archivo actual','<details><summary>Ver fila original cotejada</summary>'+cells+'<p>SHA-256 del original: <code>'+E(c['source_sha256'])+'</code></p><p>Huella de señal: <code>'+E(f['fingerprint'])+'</code></p></details>'])
 text='''<!doctype html><html lang="es"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>MindTEC · Cambios de cobertura entre exportaciones</title><style>body{background:#f1f5fa;color:#20354e;font:15px/1.55 system-ui;margin:0}main{max-width:1200px;margin:auto;padding:24px}section{background:white;border:1px solid #d8e3ef;padding:20px;margin:18px 0;border-radius:12px}h1{font-size:28px}h2{font-size:21px}.stats{display:flex;gap:12px;flex-wrap:wrap}.stats div{flex:1;min-width:170px;padding:15px;background:#edf3fa;border-radius:8px}.stats b{font-size:30px;display:block}.notice{padding:16px;background:#fff4dc;border-left:5px solid #cd942d}.scroll{overflow:auto}table{border-collapse:collapse;width:100%;font-size:13px}td,th{padding:11px;text-align:left;border-bottom:1px solid #dfe6ee;vertical-align:top}th{background:#eef3fa}small{color:#536c86}code{overflow-wrap:anywhere;font-size:12px}summary{color:#285ab0;cursor:pointer}a{color:#285ab0}</style><main><p>MindTEC · Anexo de auditoría · archivos del 13 y 16 de noviembre de 2026</p><h1>Las filas comunes no cambiaron; la cobertura de la exportación sí</h1><p>Comparación de las mismas visitas del corte actual, con la misma política histórica en ambos archivos.</p>'''
 text+='<div class="stats">'+''.join('<div><b>'+E(v)+'</b>'+E(label)+'</div>' for v,label in [(len(changes),'Diferencias de presencia de filas'),(len({c['internal_id'] for c in changes}),'Visitas con diferencias'),(len({c['brand_code'] for c in changes}),'Códigos de marca afectados'),(len(result['eligible_current_visit_ids']),'Visitas incluidas')])+'</div>'
 text+='<p class="notice">Un MAE o RMSE de cero solo describe las celdas numéricas emparejadas. No prueba igualdad de todas las filas ni de los denominadores. Las ausencias de este anexo no acreditan bajas reales de producto, errores de campo ni fraude.</p>'
 text+='<section><h2>Qué cambió en los registros exportados</h2><p>Filas de marcas de las mismas visitas: <b>'+E(result['previous_rows_same_current_visits'])+' → '+E(result['current_rows_same_current_visits'])+'</b>. Diferencia en subtotales conocidos: <b>'+E(shelf)+' caras en góndola</b> y <b>'+E(cold)+' caras en frío</b>.</p><p>Estos son subtotales de valores efectivamente registrados. Los vacíos y las claves ambiguas se cuentan aparte; no se imputan como cero. No son una variación comercial ni un KPI del universo mensual. Las visitas ausentes de todo el archivo actual y la visita históricamente excluida no entran en este contraste.</p>'+table(['Mes','Categoría','Filas anterior → actual','Góndola: subtotal conocido','Frío: subtotal conocido'],groups)+'</section>'
 text+='<section><h2>Filas que explican la diferencia</h2><p>Cada fila se cotejó con las celdas del XLSX conservado. La causa de su ausencia o incorporación requiere confirmar filtros, revisión y catálogo en origen. Ninguna señal se ha cerrado automáticamente.</p>'+table(['Marca / categoría','ID interno / Kobo','Mes','Presencia en exportación','Trazabilidad'],detail)+'</section>'
 text+='<section><h2>Fuentes y alcance</h2><p>Ejecución del anexo: <code>'+E(run['id'])+'</code></p><p>Ejecución de colecta: <code>'+E(rules['source_run_id'])+'</code></p><p>Original actual: <code>'+E(result['current_source_sha256'])+'</code></p><p>Original anterior: <code>'+E(result['previous_source_sha256'])+'</code></p><p>Cierre de custodia: <code>'+E(head)+'</code></p><p>Informe calculado localmente; verificar correspondencia con un archivo no prueba la veracidad de lo observado en la tienda.</p></section></main></html>'
 output.parent.mkdir(parents=True,exist_ok=True)
 with output.open('x',encoding='utf-8') as f:f.write(text)
 return {'output':str(output),'run_id':run['id'],'presence_changes':len(changes),'registered_shelf_delta':shelf,'registered_cold_delta':cold}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--runtime',required=True,type=Path);p.add_argument('--output',required=True,type=Path);p.add_argument('--run-id');a=p.parse_args();print(engine.canonical(export(a.runtime,a.output,a.run_id)))
