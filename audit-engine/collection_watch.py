"""Observe one explicitly selected normalized XLSX; retain cuts locally, never send."""
import argparse,json,os,time
from pathlib import Path
import engine,collection_adapter,collection_audit,invoice_adapter,supervisor

LOADED={'engine.py':engine.IMPLEMENTATION_BYTES,'collection_adapter.py':collection_adapter.IMPLEMENTATION_BYTES,'collection_audit.py':collection_audit.IMPLEMENTATION_BYTES,'invoice_adapter.py':Path(invoice_adapter.__file__).read_bytes(),'supervisor.py':supervisor.IMPLEMENTATION_BYTES,Path(__file__).name:Path(__file__).read_bytes()}

def bounded(path,limit):
 path=Path(path);before=path.stat()
 with path.open('rb') as f:raw=f.read(limit+1)
 after=path.stat()
 if len(raw)>limit:raise ValueError('Selected input exceeds size limit')
 if (before.st_size,before.st_mtime_ns)!=(after.st_size,after.st_mtime_ns):raise ValueError('Selected input changed during read')
 return raw

def mapping(raw):
 value=engine.load_json_bytes(raw)
 if not isinstance(value,dict) or not isinstance(value.get('rows'),list):raise ValueError('Explicit internal-ID to Kobo crosswalk required')
 result={};seen=set()
 for row in value['rows']:
  internal=collection_audit.identifier(row.get('internal_id'));kobo=collection_audit.identifier(row.get('kobo_id'))
  if not internal or not kobo or internal in result or kobo in seen:raise ValueError('Crosswalk identities must be complete and one-to-one')
  result[internal]=kobo;seen.add(kobo)
 if not result:raise ValueError('Empty identity crosswalk')
 return result

def validate(cut):
 tables=collection_audit.tables(cut)
 required={'visits':['ID envío','Mes','Sticker','Estado de entrega'],'shops':['ID envío','Mes','Sticker'],'brands':['ID envío','Mes','Sticker','Subcategoría (código)','Marca (código)','Marca','Caras en góndola','Caras en frío'],'prices':['ID envío','Mes','Sticker','Dónde','Código Kobo','ID SKU','SKU (maestro)','Precio Bs'],'companies':['ID envío','Mes','Sticker','Empresa (código)','Empresa','Quiebre']}
 for role,entry in tables.items():
  if any(h not in entry['table']['headers'] for h in required[role]):raise ValueError('Required collection headers missing: '+role)
  if entry['table'].get('formula_cells_using_cached_values'):raise ValueError('Formula caches are not accepted as original observations')
 if not tables['visits']['rows']:raise ValueError('Empty visit export cannot become an accepted cut')
 for row in tables['visits']['rows']:
  month=row['values'].get('Mes')
  if not isinstance(month,str) or len(month)!=7 or not month[:4].isdigit() or month[4]!='-' or month[5:] not in [f'{i:02}' for i in range(1,13)]:raise ValueError('Visit month must be explicit YYYY-MM')
 return cut

def object_bytes(e,digest):
 row=e.db.execute('SELECT object_path FROM snapshots WHERE hash=?',(digest,)).fetchone()
 if not row:raise ValueError('Retained evidence missing')
 raw=(e.root/row[0]).read_bytes()
 if engine.sha(raw)!=digest:raise ValueError('Retained evidence hash differs')
 return raw

class Observer:
 def __init__(self,source,policy,crosswalk,runtime,initial_reference=None):
  self.source=Path(source).resolve();self.policy=Path(policy).resolve();self.crosswalk=Path(crosswalk).resolve();self.runtime=Path(runtime).resolve();self.reference=Path(initial_reference).resolve() if initial_reference else None
  if any(p.is_relative_to(self.runtime) for p in [self.source,self.policy,self.crosswalk]+([self.reference] if self.reference else [])):raise ValueError('Inputs must be outside evidence runtime')
  self.series=engine.sha(engine.canonical({'source':str(self.source),'policy':str(self.policy),'crosswalk':str(self.crosswalk),'initial_reference':str(self.reference) if self.reference else None}))
  self.bundle=engine.code_bundle(LOADED);self.last_accepted=None
 def prior(self):
  with engine.Engine(self.runtime) as e:
   e.verify()
   for row in e.db.execute('SELECT event_json FROM events ORDER BY seq DESC'):
    event=engine.load_json_bytes(row[0].encode())
    if event['action']!='collection.observer.accepted':continue
    payload=event['payload']
    if payload.get('series')!=self.series:raise ValueError('Runtime belongs to another selected collection source')
    run=e.db.execute('SELECT * FROM runs WHERE id=?',(payload['run_id'],)).fetchone()
    if not run:raise ValueError('Accepted collection run missing')
    rules=engine.load_json_bytes(run['rules_json'].encode());refs=rules['reference_sources'];result=engine.load_json_bytes(object_bytes(e,run['snapshot_hash']))
    if rules.get('kind')!='collection_observer' or rules.get('series')!=self.series or rules.get('context_sha256')!=payload['context_sha256'] or result['source']['original_sha256']!=payload['source_sha256'] or refs['current_workbook']!=payload['source_sha256']:raise ValueError('Accepted collection source binding differs')
    if (result.get('previous_source') or {}).get('original_sha256')!=refs.get('reference_workbook'):raise ValueError('Accepted comparison reference binding differs')
    return {**payload,'rules':rules,'result':result,'source':object_bytes(e,refs['current_workbook']),'reference':object_bytes(e,refs['reference_workbook']) if 'reference_workbook' in refs else None}
  return None
 def slim(self,prior):return {k:prior[k] for k in ['run_id','source_sha256','context_sha256']} if prior else None
 def poll(self):
  h={'pid':os.getpid(),'checked_at':engine.now(),'mode':'selected_collection_xlsx_observer','network_delivery':False,'last_accepted':self.last_accepted,'custody_verified':False};candidate={}
  try:
   if any(Path(__file__).with_name(name).read_bytes()!=raw for name,raw in LOADED.items()):raise ValueError('Implementation changed; restart collection observer')
   prior=self.prior()
   if self.last_accepted and not prior:raise ValueError('Previously accepted collection disappeared')
   self.last_accepted=self.slim(prior);h.update(last_accepted=self.last_accepted,custody_verified=prior is not None)
   source=bounded(self.source,25000000);candidate['candidate_workbook']=(source,'.xlsx')
   policy_raw=bounded(self.policy,100000);candidate['candidate_policy']=(policy_raw,'.json');policy=engine.load_json_bytes(policy_raw)
   if policy.get('schema')!='mindtec-audit-policy/1' or not isinstance(policy.get('exclusions'),list):raise ValueError('Historical exclusion policy required')
   cross_raw=bounded(self.crosswalk,2000000);candidate['candidate_crosswalk']=(cross_raw,'.json');cross=mapping(cross_raw)
   context=engine.sha(engine.canonical({'policy':engine.sha(policy_raw),'crosswalk':engine.sha(cross_raw),'implementation':engine.sha(self.bundle)}));source_sha=engine.sha(source)
   if not prior or source_sha!=prior['source_sha256'] or context!=prior['context_sha256']:
    current=validate(collection_adapter.workbook_tables(self.source,source))
    if prior:reference=prior['source'] if source_sha!=prior['source_sha256'] else prior['reference']
    else:reference=bounded(self.reference,25000000) if self.reference else None
    if reference is not None:candidate['candidate_reference']=(reference,'.xlsx')
    before=validate(collection_adapter.workbook_tables('retained-reference.xlsx',reference)) if reference is not None else None
    result=collection_audit.evaluate(current,before,cross,policy)
    refs={'current_workbook':(source,'.xlsx'),'crosswalk':(cross_raw,'.json'),'policy_file':(policy_raw,'.json'),'implementation':(self.bundle,'.json')}
    if reference is not None:refs['reference_workbook']=(reference,'.xlsx')
    rules={'kind':'collection_observer','version':'1','series':self.series,'context_sha256':context,'data_changed':prior is not None and source_sha!=prior['source_sha256'],'reference_sources':{k:engine.sha(v[0]) for k,v in refs.items()}}
    with engine.Engine(self.runtime) as e:
     accepted=e.record_result(engine.canonical(result).encode(),policy,rules,result['findings'],{'coverage':result['coverage'],'table_counts':result['table_counts'],'network_delivery':False},refs)
     payload={'series':self.series,'run_id':accepted['run_id'],'source_sha256':source_sha,'context_sha256':context}
     e.db.execute('BEGIN IMMEDIATE')
     try:e.append('collection.observer.accepted',payload);e.db.execute('COMMIT')
     except Exception:e.db.execute('ROLLBACK');raise
    prior=self.prior()
   self.last_accepted=self.slim(prior)
   h.update(status='healthy',run_id=prior['run_id'],last_accepted=self.last_accepted,custody_verified=True,coverage=prior['result']['coverage'],finding_count=len(prior['result']['findings']))
  except Exception as error:
   h.update(status='degraded',reason=str(error),error_type=type(error).__name__,last_accepted=self.last_accepted)
   try:
    with engine.Engine(self.runtime) as e:
     payload={'series':self.series,'error_type':type(error).__name__,'reason':str(error),'last_accepted':self.last_accepted,'retained_inputs':{k:engine.sha(v[0]) for k,v in candidate.items()}}
     last=e.db.execute('SELECT event_json FROM events ORDER BY seq DESC LIMIT 1').fetchone()
     if not last or engine.load_json_bytes(last[0].encode()).get('payload')!=payload:
      e.db.execute('BEGIN IMMEDIATE')
      try:
       for raw,ext in candidate.values():
        obj=e.store_object(raw,ext);e.db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?)',(engine.sha(raw),str(obj.relative_to(e.root))))
       e.append('collection.observer.rejected',payload);e.db.execute('COMMIT')
      except Exception:e.db.execute('ROLLBACK');raise
   except Exception:h['failure_history_unverified']=True
  supervisor.atomic(self.runtime/'health.json',h);return h

def watch(observer,interval=30,iterations=None):
 if isinstance(interval,bool) or not isinstance(interval,(int,float)) or not 10<=interval<=3600:raise ValueError('Interval must be 10 to 3600 seconds')
 with supervisor.exclusive(observer.runtime/'collection-observer.lock'):
  count=0
  while True:
   h=observer.poll();count+=1
   if iterations is not None and count>=iterations:return h
   time.sleep(interval)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['source','policy','crosswalk','runtime']:p.add_argument('--'+name,required=True,type=Path)
 p.add_argument('--initial-reference',type=Path);p.add_argument('--interval',type=float,default=30);p.add_argument('--iterations',type=int);a=p.parse_args()
 print(engine.canonical(watch(Observer(a.source,a.policy,a.crosswalk,a.runtime,a.initial_reference),a.interval,a.iterations)))
