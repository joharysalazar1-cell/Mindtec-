"""Prepare coherent, immutable synchronization evidence. This module never sends."""
import argparse,json,re,urllib.parse
from pathlib import Path
import engine,lineage_bundle,supervisor,windows_job
from supervisor import exclusive

VERSION='mindtec-sync-outbox/1.0.0'
LOADED={'engine.py':engine.IMPLEMENTATION_BYTES,'lineage_bundle.py':Path(lineage_bundle.__file__).read_bytes(),'supervisor.py':supervisor.IMPLEMENTATION_BYTES,'windows_job.py':Path(windows_job.__file__).read_bytes(),Path(__file__).name:Path(__file__).read_bytes()}

def require(value,message):
 if not value:raise ValueError(message)

def target(origin,project_id):
 try:
  u=urllib.parse.urlsplit(origin)
  valid=isinstance(origin,str) and origin.startswith('https://') and not any(c.isspace() or ord(c)<32 for c in origin) and u.scheme=='https' and u.hostname and ':' not in u.hostname and u.port in (None,443) and not u.username and not u.password and u.path in ('','/') and not u.query and not u.fragment
 except (ValueError,TypeError):valid=False
 require(valid,'A credential-free HTTPS Site origin is required')
 require(isinstance(project_id,str) and re.fullmatch(r'appgprj_[a-zA-Z0-9]+',project_id),'Explicit Site project ID required')
 return {'origin':'https://'+u.hostname.lower(),'project_id':project_id}

def capture(runtime):
 root=Path(runtime).resolve();require((root/'audit.sqlite').is_file(),'An existing accepted source runtime is required')
 with engine.Engine(root) as e:
  # Freeze each ledger prefix while reading its run and object catalog. The
  # three prefixes are separately observed; lineage identities join the cuts.
  e.db.execute('BEGIN')
  try:
   head=e.verify();row=e.db.execute('SELECT * FROM runs ORDER BY at DESC LIMIT 1').fetchone();require(row is not None,'No accepted source run')
   run=dict(row);catalog={r['hash']:str((root/r['object_path']).resolve()) for r in e.db.execute('SELECT * FROM snapshots')}
   require(all(Path(p).is_relative_to(root) for p in catalog.values()),'Source artifact leaves its custody directory')
   events=[dict(r) for r in e.db.execute('SELECT seq,event_json,hash FROM events ORDER BY seq')]
  finally:e.db.execute('ROLLBACK')
 return {'root':root,'run':run,'head':head,'catalog':catalog,'events':events}

def prepare(invoice_runtime,scan_runtime,lineage_runtime,runtime,origin,project_id):
 destination=target(origin,project_id);output=Path(runtime).resolve();roots=[Path(p).resolve() for p in [invoice_runtime,scan_runtime,lineage_runtime]]
 require(len(set(roots))==3,'Distinct source runtimes required')
 require(all(not output.is_relative_to(p) and not p.is_relative_to(output) for p in roots),'Outbox custody must be separate from source runtimes')
 require(all(Path(__file__).with_name(n).read_bytes()==b for n,b in LOADED.items()),'Outbox implementation changed; restart before preparing')
 # A pending coherent package is local state, not an assertion of remote receipt.
 with exclusive(output/'outbox.lock'):
  states={name:capture(path) for name,path in zip(['invoice','scan','lineage'],roots)};cache={};references={};descriptors={};sizes={}
  def content(state,hash_):
   require(isinstance(hash_,str) and re.fullmatch(r'[a-f0-9]{64}',hash_),'Invalid artifact digest')
   require(hash_ in state['catalog'],'Source artifact missing from custody catalog')
   path=Path(state['catalog'][hash_]);require(path.suffix in ('.json','.xlsx'),'Unsupported source evidence format')
   if hash_ not in cache:
    with path.open('rb') as f:raw=f.read(100000001)
    require(len(raw)<=100000000,'Source artifact exceeds outbox limit');require(engine.sha(raw)==hash_,'Source artifact changed during outbox capture');cache[hash_]=raw
   return cache[hash_],path.suffix
  def add(role,raw,extension='.json',meaning='preserved_source_bytes'):
   require(len(raw)<=100000000,'Outbox object exceeds limit');hash_=engine.sha(raw);sizes[hash_]=len(raw);require(sum(sizes.values())<=400000000,'Outbox package exceeds total evidence limit');references[role]=(raw,extension);descriptors[role]={'sha256':hash_,'bytes':len(raw),'extension':extension,'meaning':meaning};return hash_
  def add_object(role,state,hash_):
   raw,extension=content(state,hash_);return add(role,raw,extension)
  runs={};data={}
  for name,state in states.items():
   r=state['run'];rules=json.loads(r['rules_json']);runs[name]={'local_run_id':r['id'],'source_sha256':r['snapshot_hash'],'ledger_head':state['head']}
   data[name]=engine.load_json_bytes(content(state,r['snapshot_hash'])[0])
   require(rules.get('kind')=={'invoice':'invoice','lineage':'kpi_lineage'}.get(name,rules.get('kind')),'Unexpected source audit family')
   if name=='scan':require('envios' in data[name] and 'rules' in rules and 'kind' not in rules,'Scan source audit required')
   add_object(name+'.source',state,r['snapshot_hash'])
   add(name+'.run_record',engine.canonical(r).encode(),meaning='exact_database_record_fields')
   add(name+'.policy',r['policy_json'].encode(),meaning='stored_canonical_policy_not_original_config_bytes')
   add(name+'.rules',r['rules_json'].encode(),meaning='stored_rules')
   add(name+'.findings',r['findings_json'].encode(),meaning='stored_findings')
   add(name+'.ledger_prefix',engine.canonical(state['events']).encode(),meaning='event_text_and_hash_prefix_historical_objects_not_all_included')
   for role,hash_ in rules.get('reference_sources',{}).items():add_object(name+'.reference.'+role,state,hash_)
  lineage=data['lineage'];require(lineage.get('schema')=='mindtec-kpi-lineage/1','Accepted KPI lineage source required')
  for name in ['invoice','scan']:
   declared=lineage.get(name+'_run',{});observed=runs[name]
   require(declared.get('id')==observed['local_run_id'] and declared.get('source_sha256')==observed['source_sha256'],'Lineage has not accepted the current '+name+' cut; preserve the previous outbox package')
   # Lineage can refer to an earlier valid prefix of the same accepted run;
   # later human reviews or observer events do not change the source identity.
   heads={'GENESIS',*(e['hash'] for e in states[name]['events'])};require(declared.get('ledger_head') in heads,'Lineage names an unknown source ledger prefix')
   for role in ['source','findings']:
    require(descriptors.get('lineage.reference.'+name+'_'+role,{}).get('sha256')==descriptors[name+'.'+role]['sha256'],'Lineage preserved '+name+' '+role+' differs from the selected accepted run')
  invoice_rules=json.loads(states['invoice']['run']['rules_json']);require(invoice_rules.get('source_workbook_verified') is True,'Current invoice original must be verified locally')
  require('invoice.reference.current_workbook' in descriptors,'Current invoice original is missing')
  require(descriptors['invoice.reference.current_workbook']['sha256']==data['invoice'].get('provenance',{}).get('original_sha256'),'Invoice original provenance mismatch')
  if 'invoice.reference.previous_cut' in descriptors:
   require(invoice_rules.get('reference_workbook_verified') is True and 'invoice.reference.previous_workbook' in descriptors,'Comparable invoice reference requires its verified original')
   previous=json.loads(references['invoice.reference.previous_cut'][0]);require(previous.get('provenance',{}).get('original_sha256')==descriptors['invoice.reference.previous_workbook']['sha256'],'Previous invoice original provenance mismatch')
  parents={role:references['lineage.reference.'+role][0] for role in lineage_bundle.PARENT_NAMES}
  bundle=lineage_bundle.project(parents);add('web.lineage_dependencies',engine.canonical(bundle).encode(),meaning='derived_projection_of_preserved_lineage_parents_not_their_original_bytes')
  add('outbox.implementation',engine.code_bundle(LOADED),meaning='exact_outbox_implementation_bundle')
  unique={v['sha256']:v['bytes'] for v in descriptors.values()};require(sum(unique.values())<=400000000,'Outbox package exceeds total evidence limit')
  manifest={'schema':'mindtec-sync-package/1','version':VERSION,'target':destination,'runs':runs,'artifacts':descriptors,'state':'prepared_not_sent','limits':['Source ledgers were observed separately; exact accepted run identities join their cuts.','Ledger prefixes preserve event text and hashes; historical objects beyond selected run references are not all included.','Local run IDs do not imply matching remote evaluator IDs or remote acceptance.','No original value, exclusion or human review is changed. A signal is not proof of fraud.','No credential, request or remote receipt is created by preparing this package.']}
  raw=engine.canonical(manifest).encode();policy={'schema':'mindtec-sync-package-policy/1','version':'1.0.0','mode':'local_preparation_only'};rules={'kind':'sync_outbox','engine_version':VERSION,'implementation_sha256':engine.sha(engine.code_bundle(LOADED)),'reference_sources':{role:v['sha256'] for role,v in descriptors.items()}}
  with engine.Engine(output) as e:result=e.record_result(raw,policy,rules,[],{'unique_objects':len(unique),'evidence_bytes':sum(unique.values()),'state':'prepared_not_sent'},references)
  return {**{k:v for k,v in result.items() if k!='findings'},'state':'prepared_not_sent','artifacts':len(descriptors),'unique_objects':len(unique),'evidence_bytes':sum(unique.values())}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--invoice-runtime',required=True,type=Path);p.add_argument('--scan-runtime',required=True,type=Path);p.add_argument('--lineage-runtime',required=True,type=Path);p.add_argument('--runtime',required=True,type=Path);p.add_argument('--origin',required=True);p.add_argument('--project-id',required=True);a=p.parse_args();print(engine.canonical(prepare(a.invoice_runtime,a.scan_runtime,a.lineage_runtime,a.runtime,a.origin,a.project_id)))
