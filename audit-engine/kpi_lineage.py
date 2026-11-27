"""Link verified findings to declared KPI inputs, without inferring numeric impact."""
import argparse,collections,json
from pathlib import Path
import engine,invoice_core
LOADED_SOURCES={'engine.py':engine.IMPLEMENTATION_BYTES,'invoice_core.py':Path(invoice_core.__file__).read_bytes(),Path(__file__).name:Path(__file__).read_bytes()}

def require(value,message):
 if not value:raise ValueError(message)

def invoice_links(kpis,scope,cut,findings,source_hash):
 require(scope.get('sha256_facturas')==cut.get('provenance',{}).get('original_sha256'),'KPI invoice workbook differs from the audited original')
 rows=invoice_core.row_values(invoice_core.validate_cut(cut));keys=collections.Counter(invoice_core.line_key(v) for v in rows if invoice_core.line_key(v));by_source={r['source_row']:invoice_core.line_key(v) for r,v in zip(cut['rows'],rows)}
 by_key=collections.defaultdict(list)
 for finding in findings:
  ev=finding['evidence'];require(ev.get('current_source_sha256')==source_hash,'Invoice finding cut mismatch')
  require(all(r in by_source for r in ev.get('source_rows',[])),'Finding points to an absent current row')
  # Use row references in the verified run, not a display ID split on punctuation.
  referenced={by_source[r] for r in ev.get('source_rows',[]) if r in by_source and by_source[r]}
  for key in referenced:by_key[key].append(finding)
 out=[]
 for kpi in kpis:
  declared=kpi.get('operativo',{}).get('lineas_factura_relacionadas',[]);require(isinstance(declared,list) and all(isinstance(k,str) for k in declared),'Declared invoice dependencies must be strings')
  dependencies=list(dict.fromkeys(declared));links=[]
  for key in dependencies:
   for f in by_key.get(key,[]):links.append({'kind':'declared_invoice_input','line_key':key,'key_occurrences':keys[key],'finding_fingerprint':f['fingerprint'],'rule':f['rule'],'severity':f['severity'],'paths':f['evidence']['paths'],'numeric_impact':'not_established'})
  out.append({'kpi_id':kpi['id'],'month':kpi['mes'],'brand':kpi['marca'],'category':kpi['categoria'],'indicator':kpi['indicador'],'published':kpi.get('publicado_original'),'operational_value':kpi.get('operativo',{}).get('valor'),'declared_dependencies':len(dependencies),'missing_dependencies':[k for k in dependencies if k not in keys],'ambiguous_dependencies':[k for k in dependencies if keys[k]>1],'links':links,'status':'declared_inputs_with_signals' if links else 'no_signals_in_declared_invoice_inputs' if dependencies else 'no_declared_invoice_dependency','numeric_impact':'not_established'})
 return out

def perfect_store_links(details,manifest,scan,scan_hash,findings):
 source=next((s for s in manifest.get('fuentes',[]) if s.get('archivo')=='cuestionarios_normalizados_2026-11-13.json'),None)
 require(source and source.get('sha256')==scan_hash,'Perfect Store and Scan cuts differ')
 records=collections.defaultdict(list)
 for index,record in enumerate(scan['envios']):records[str(record['envioKobo'])].append((index,record))
 signals=collections.defaultdict(list)
 for f in findings:signals[f['evidence']['record_index']].append(f)
 out=[]
 for position,row in enumerate(details):
  candidates=records.get(str(row['id_envio']),[]);components=[]
  for component in row['componentes']:
   verified=[];unresolved=[];linked={}
   for source in component.get('fuentes',[]):
    path=source['ruta'];answers=[]
    if len(candidates)==1:answers=[a for a in candidates[0][1]['respuestas'] if a['ruta']==path]
    if len(answers)!=1 or engine.canonical(answers[0]['valor'])!=engine.canonical(source['valor']):unresolved.append(path);continue
    verified.append(path)
    for finding in signals.get(candidates[0][0],[]):
     if path in finding['evidence']['paths']:
      linked[finding['fingerprint']]={'kind':'component_source_overlap','finding_fingerprint':finding['fingerprint'],'rule':finding['rule'],'severity':finding['severity'],'record_index':candidates[0][0],'matched_paths':sorted(set(verified)&set(finding['evidence']['paths'])),'numeric_impact':'not_established'}
   # Recompute path intersections after all sources, avoiding order-dependent evidence.
   for f in signals.get(candidates[0][0] if len(candidates)==1 else None,[]):
    if f['fingerprint'] in linked:linked[f['fingerprint']]['matched_paths']=sorted(set(verified)&set(f['evidence']['paths']))
   components.append({'component':component['componente'],'state':component['estado'],'value':component['valor'],'weight':component['peso'],'verified_paths':sorted(set(verified)),'unresolved_paths':sorted(set(unresolved)),'links':list(linked.values())})
  out.append({'detail_index':position,'month':row['mes'],'category':row['categoria'],'brand':row['marca'],'company':row.get('empresa'),'record_id':str(row['id_envio']),'record_matches':len(candidates),'components':components})
 return out

def accepted(runtime):
 with engine.Engine(runtime) as e:
  head=e.verify();run=e.db.execute('SELECT * FROM runs ORDER BY at DESC LIMIT 1').fetchone();require(run is not None,'No accepted run')
  entry=e.db.execute('SELECT object_path FROM snapshots WHERE hash=?',(run['snapshot_hash'],)).fetchone();require(entry is not None,'Missing source catalog entry');raw=(e.root/entry[0]).read_bytes()
  return {'id':run['id'],'source_hash':run['snapshot_hash'],'source':engine.load_json_bytes(raw),'source_raw':raw,'findings':json.loads(run['findings_json']),'rules':json.loads(run['rules_json']),'ledger_head':head}

def execute(invoice_runtime,scan_runtime,kpi_dir,perfect_store_dir,runtime):
 require(all(Path(__file__).with_name(name).read_bytes()==content for name,content in LOADED_SOURCES.items()),'Implementation changed; restart lineage evaluation')
 invoice=accepted(invoice_runtime);scan=accepted(scan_runtime)
 require(invoice['rules'].get('kind')=='invoice','Invoice run required');require('envios' in scan['source'],'Scan run required')
 kp=Path(kpi_dir);ps=Path(perfect_store_dir)
 paths={'kpis':kp/'resultados_12_KPI.json','kpi_scope':kp/'fuentes_y_alcance.json','perfect_store_details':ps/'detalle_por_tienda.json','perfect_store_manifest':ps/'manifiesto.json'}
 raw={role:path.read_bytes() for role,path in paths.items()};data={role:engine.load_json_bytes(content) for role,content in raw.items()}
 # Every finding belongs to the verified current source. Different cuts never join by ID alone.
 require(all(f['evidence'].get('current_source_sha256')==invoice['source_hash'] for f in invoice['findings']),'Invoice finding cut mismatch')
 invoice_result=invoice_links(data['kpis'],data['kpi_scope'],invoice['source'],invoice['findings'],invoice['source_hash'])
 ps_result=perfect_store_links(data['perfect_store_details'],data['perfect_store_manifest'],scan['source'],scan['source_hash'],scan['findings'])
 result={'schema':'mindtec-kpi-lineage/1','invoice_run':{'id':invoice['id'],'source_sha256':invoice['source_hash'],'ledger_head':invoice['ledger_head']},'scan_run':{'id':scan['id'],'source_sha256':scan['source_hash'],'ledger_head':scan['ledger_head']},'invoice_kpis':invoice_result,'perfect_store':ps_result,'limits':['Links identify shared declared inputs; numeric impact is not established.','No KPI, original answer, exclusion or human decision is changed.','No declared dependencies or no matching signals does not prove validation.','Historical KPI and recent Perfect Store cuts retain their separate dates.']}
 summary={'kpi_rows':len(invoice_result),'indicators':len({r['indicator'] for r in invoice_result}),'kpi_rows_with_links':sum(bool(r['links']) for r in invoice_result),'invoice_links':sum(len(r['links']) for r in invoice_result),'missing_invoice_dependencies':sum(len(r['missing_dependencies']) for r in invoice_result),'perfect_store_rows':len(ps_result),'perfect_store_links':sum(len(c['links']) for r in ps_result for c in r['components']),'unresolved_component_paths':sum(len(c['unresolved_paths']) for r in ps_result for c in r['components'])}
 raw.update(invoice_source=invoice['source_raw'],scan_source=scan['source_raw'],invoice_findings=engine.canonical(invoice['findings']).encode(),scan_findings=engine.canonical(scan['findings']).encode(),implementation=Path(__file__).read_bytes())
 references={role:(content,'.json' if role!='implementation' else '.py') for role,content in raw.items()}
 # The common object store accepts JSON/XLSX only; package code as exact base64 bytes.
 references['implementation']=(engine.code_bundle(LOADED_SOURCES),'.json')
 result_raw=engine.canonical(result).encode();policy={'schema':'mindtec-lineage-policy/1','version':'1.0.0-explicit-input-links','numeric_impact':'not_established'}
 rules={'kind':'kpi_lineage','engine_version':'lineage/1.0.0','implementation_sha256':engine.sha(engine.code_bundle(LOADED_SOURCES)),'reference_sources':{k:engine.sha(v[0]) for k,v in references.items()}}
 with engine.Engine(runtime) as e:stored=e.record_result(result_raw,policy,rules,[],summary,references)
 return {**stored,'summary':summary}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--invoice-runtime',type=Path,required=True);p.add_argument('--scan-runtime',type=Path,required=True);p.add_argument('--kpi-dir',type=Path,required=True);p.add_argument('--perfect-store-dir',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);a=p.parse_args();r=execute(a.invoice_runtime,a.scan_runtime,a.kpi_dir,a.perfect_store_dir,a.runtime);print(engine.canonical({k:v for k,v in r.items() if k!='findings'}))
