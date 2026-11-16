"""Explain export coverage changes separately from changes on matched cells."""
import argparse,collections
from pathlib import Path
import engine,collection_adapter,collection_audit,collection_watch,invoice_adapter

IMPLEMENTATION_BYTES=Path(__file__).read_bytes()

def evaluate(current,previous,crosswalk,policy):
 now=collection_audit.tables(current);old=collection_audit.tables(previous)
 exclusions={str(e['id']) for e in policy.get('exclusions',[])}
 parent_groups=collections.defaultdict(list)
 for r in now['visits']['rows']:parent_groups[collection_audit.identifier(r['values'].get('ID envío'))].append(r)
 eligible={eid for eid,rows in parent_groups.items() if eid and len(rows)==1 and eid in crosswalk and crosswalk[eid] not in exclusions}
 parent_month={eid:parent_groups[eid][0]['values']['Mes'] for eid in eligible}
 by_cut=[];rows_by_cut=[]
 for cut in [old,now]:
  grouped=collections.defaultdict(list)
  for row in cut['brands']['rows']:
   eid=collection_audit.identifier(row['values'].get('ID envío'))
   if eid in eligible and row['values'].get('Mes')==parent_month[eid]:grouped[collection_audit.row_key('brands',row)].append(row)
  # Ambiguous identities remain visible but do not become silent numeric pairs.
  by_cut.append(grouped);rows_by_cut.append([r for rows in grouped.values() for r in rows])
 categories=collections.defaultdict(lambda:[[],[]]);presence=[]
 for side,rows in enumerate(rows_by_cut):
  for r in rows:categories[(r['values'].get('Mes'),r['values'].get('Subcategoría (código)'))][side].append(r)
 for key in sorted(set(by_cut[0])|set(by_cut[1]),key=engine.canonical):
  before=by_cut[0].get(key,[]);after=by_cut[1].get(key,[])
  if key is None or len(before)>1 or len(after)>1 or bool(before)==bool(after):continue
  side=0 if before else 1;row=(before or after)[0];table=(old if side==0 else now)['brands']['table'];source=(previous if side==0 else current)['provenance']['original_sha256']
  columns=['ID envío','Mes','Subcategoría (código)','Marca (código)','Marca','Caras en góndola','Caras en frío','SKUs (códigos Kobo)']
  cells=[collection_audit.cell_ref(table,row,col) for col in columns if col in table['headers']]
  presence.append({'state':'only_previous_export' if before else 'only_current_export','internal_id':key[0],'kobo_id':crosswalk[key[0]],'month':key[1],'category':row['values'].get('Subcategoría (código)'),'brand':row['values'].get('Marca'),'brand_code':row['values'].get('Marca (código)'),'source_sha256':source,'source_row':row['source_row'],'cells':cells,'meaning':'Row present in only one export of the same visits; not proof of a product addition/removal or fraud.'})
 groups=[]
 for (month,category),sides in sorted(categories.items(),key=lambda x:engine.canonical(x[0])):
  group={'month':month,'category':category,'previous_rows':len(sides[0]),'current_rows':len(sides[1]),'measures':{}}
  for field in ['Caras en góndola','Caras en frío']:
   stats=[]
   for side,rows in enumerate(sides):
    measured=[r for r in rows if collection_audit.numeric(r['values'].get(field),integer=True) and len(by_cut[side].get(collection_audit.row_key('brands',r),[]))==1]
    stats.append({'registered_subtotal':sum(r['values'][field] for r in measured),'valid_unambiguous_rows':len(measured),'missing_or_ambiguous_rows':len(rows)-len(measured),'cells':[collection_audit.cell_ref((old if side==0 else now)['brands']['table'],r,field) for r in measured]})
   group['measures'][field]={'previous':stats[0],'current':stats[1],'registered_subtotal_delta':stats[1]['registered_subtotal']-stats[0]['registered_subtotal'],'state':'registered_subtotal_change_only_not_a_population_kpi'}
  groups.append(group)
 return {'schema':'mindtec-collection-export-impact/1','current_source_sha256':current['provenance']['original_sha256'],'previous_source_sha256':previous['provenance']['original_sha256'],'eligible_current_visit_ids':sorted(eligible),'previous_rows_same_current_visits':len(rows_by_cut[0]),'current_rows_same_current_visits':len(rows_by_cut[1]),'presence_changes':presence,'category_subtotals':groups,'limits':['The current export defines the compared visits; other visits and absent months are not deletions.','Historical exclusions are applied identically to both sides.','Missing or ambiguous values are omitted from registered subtotals and counted explicitly, never imputed as zero.','Matched-cell MAE/RMSE do not measure coverage loss or its contribution to a population KPI.','Subtotal deltas explain exported records only; they do not establish true performance or the reason for a correction.']}

def execute(source_runtime,runtime,run_id=None):
 source_runtime=Path(source_runtime).resolve();runtime=Path(runtime).resolve()
 if source_runtime.is_relative_to(runtime) or runtime.is_relative_to(source_runtime):raise ValueError('Impact custody must be separate')
 if not (source_runtime/'audit.sqlite').is_file():raise ValueError('Accepted collection custody required')
 with engine.Engine(source_runtime) as e:
  e.db.execute('BEGIN')
  try:
   e.verify();run=e.db.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone() if run_id else e.db.execute("SELECT * FROM runs WHERE json_extract(rules_json,'$.kind')='collection_observer' ORDER BY at DESC,id DESC LIMIT 1").fetchone()
   if not run:raise ValueError('Accepted collection execution not found')
   rules=engine.load_json_bytes(run['rules_json'].encode());refs=rules.get('reference_sources',{})
   if rules.get('kind')!='collection_observer' or not all(k in refs for k in ['current_workbook','reference_workbook','crosswalk','policy_file','implementation']):raise ValueError('Collection run with retained comparison sources required')
   read=lambda name:collection_watch.object_bytes(e,refs[name])
   sources={name:(read(name),'.xlsx' if name.endswith('workbook') else '.json') for name in ['current_workbook','reference_workbook','crosswalk','policy_file','implementation']}
   sources['source_run']=(engine.canonical(dict(run)).encode(),'.json')
   policy=engine.load_json_bytes(sources['policy_file'][0])
   if engine.canonical(policy)!=run['policy_json']:raise ValueError('Policy file differs from accepted policy')
   current=collection_watch.validate(collection_adapter.workbook_tables('current.xlsx',sources['current_workbook'][0]));previous=collection_watch.validate(collection_adapter.workbook_tables('previous.xlsx',sources['reference_workbook'][0]))
   result=evaluate(current,previous,collection_watch.mapping(sources['crosswalk'][0]),policy)
  finally:e.db.execute('ROLLBACK')
 bundle=engine.code_bundle({'collection_impact.py':IMPLEMENTATION_BYTES,'collection_adapter.py':collection_adapter.IMPLEMENTATION_BYTES,'collection_audit.py':collection_audit.IMPLEMENTATION_BYTES,'collection_watch.py':Path(collection_watch.__file__).read_bytes(),'invoice_adapter.py':Path(invoice_adapter.__file__).read_bytes(),'engine.py':engine.IMPLEMENTATION_BYTES})
 sources['impact_implementation']=(bundle,'.json');findings=[]
 for change in result['presence_changes']:
  f={'rule':'collection_export_row_presence_changed','rule_version':'1','severity':'medium','title':'Fila de marca presente en una sola exportación','evidence':change,'explanation':'Confirmar filtros, revisión y catálogo de origen antes de interpretar una alta o baja. Se conserva la fila original y no se cambia el KPI.','disposition':'needs_human_review'};f['fingerprint']=engine.sha(engine.canonical({'rule':f['rule'],'rule_version':'1','evidence':change}));findings.append(f)
 out_rules={'kind':'collection_export_impact','version':'1','source_run_id':run['id'],'reference_sources':{k:engine.sha(v[0]) for k,v in sources.items()}}
 with engine.Engine(runtime) as e:
  accepted=e.record_result(engine.canonical(result).encode(),policy,out_rules,findings,{'presence_changes':len(findings),'current_visit_cohort':len(result['eligible_current_visit_ids'])},sources)
  return {'run_id':accepted['run_id'],'source_run_id':run['id'],'findings':len(findings),'result':result,'ledger_head':e.verify()}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-runtime',required=True,type=Path);p.add_argument('--runtime',required=True,type=Path);p.add_argument('--run-id');p.add_argument('--output',required=True,type=Path);a=p.parse_args()
 if a.output.resolve().is_relative_to(a.runtime.resolve()) or a.output.resolve().is_relative_to(a.source_runtime.resolve()):raise ValueError('Export output must be outside custody')
 r=execute(a.source_runtime,a.runtime,a.run_id);a.output.parent.mkdir(parents=True,exist_ok=True)
 with a.output.open('x',encoding='utf-8') as f:f.write(engine.canonical(r))
 print(engine.canonical({'run_id':r['run_id'],'findings':r['findings'],'output':str(a.output.resolve())}))
