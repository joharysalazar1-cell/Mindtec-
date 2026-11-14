"""Watch an approved local invoice cut; advance only after a verified acceptance."""
import argparse,contextlib,json,os,time
from pathlib import Path
import engine,invoice_core,invoice_adapter,invoice_pipeline

def bounded(path,limit=60_000_000):
 with Path(path).open('rb') as f:raw=f.read(limit+1)
 if len(raw)>limit:raise ValueError('Input exceeds configured byte limit')
 return raw

@contextlib.contextmanager
def observer_lock(runtime):
 root=Path(runtime);root.mkdir(parents=True,exist_ok=True);f=(root/'invoice-observer.lock').open('a+b')
 if f.seek(0,2)==0:f.write(b'0');f.flush()
 f.seek(0);locked=False
 try:
  try:
   if os.name=='nt':
    import msvcrt
    msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
   else:
    import fcntl
    fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
   locked=True
  except OSError as e:raise RuntimeError('Another invoice observer owns this runtime') from e
  yield
 finally:
  if locked:
   f.seek(0)
   if os.name=='nt':msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
   else:fcntl.flock(f,fcntl.LOCK_UN)
  f.close()

def implementation():return engine.sha(engine.canonical({str(Path(m.__file__).name):engine.file_hash(m.__file__) for m in [engine,invoice_core,invoice_adapter,invoice_pipeline]}|{'observer':engine.file_hash(__file__)}))

class InvoiceObserver:
 def __init__(self,source,policy,runtime,originals,initial_reference=None):
  self.source=Path(source).resolve();self.policy=Path(policy).resolve();self.runtime=Path(runtime).resolve();self.originals=Path(originals).resolve();self.initial_reference=Path(initial_reference).resolve() if initial_reference else None
  self.series=engine.sha(str(self.source));self.code=implementation();self.last_token=None;self.last_result=None;self.last_failure=None
  self.code_bundle=engine.code_bundle({Path(m.__file__).name:Path(m.__file__).read_bytes() for m in [engine,invoice_core,invoice_adapter,invoice_pipeline]}|{Path(__file__).name:Path(__file__).read_bytes()})
 def events(self,e):
  out=[]
  for r in e.db.execute('SELECT event_json FROM events ORDER BY seq DESC'):
   event=json.loads(r[0])
   if event['action']=='invoice.observer.accepted' and event['payload'].get('series')==self.series:out.append(event['payload'])
  return out
 def artifact(self,e,hash_):
  row=e.db.execute('SELECT object_path FROM snapshots WHERE hash=?',(hash_,)).fetchone()
  if not row:raise ValueError('Accepted reference object is missing from catalog')
  path=e.root/row[0]
  if engine.file_hash(path)!=hash_:raise ValueError('Accepted reference bytes no longer match')
  return path
 def original(self,cut):
  filename=cut.get('provenance',{}).get('filename')
  if not isinstance(filename,str) or not filename or any(c in filename for c in '/\\:') or filename in ('.','..'):raise ValueError('Original workbook requires a safe basename')
  path=(self.originals/filename).resolve();path.relative_to(self.originals)
  if not path.is_file():raise ValueError('The matching original workbook has not arrived')
  return path
 def step(self):
  if implementation()!=self.code:raise RuntimeError('Implementation changed; restart invoice observer')
  raw=bounded(self.source);policy_raw=bounded(self.policy,100000)
  cut=invoice_core.validate_cut(engine.load_json_bytes(raw));invoice_core.validate_policy(engine.load_json_bytes(policy_raw))
  current_sha=engine.sha(raw);scope_sha=engine.sha(engine.canonical(cut['scope']));original=self.original(cut);original_sha=engine.file_hash(original)
  with engine.Engine(self.runtime) as e:
   events=self.events(e);head=next((p for p in events if p['scope_hash']==scope_sha),None)
   reference=None;reference_raw=None;reference_book=None
   if head:
    if head['snapshot']==current_sha:
     previous_sha=head.get('reference_snapshot');previous_book=head.get('reference_workbook')
    else:previous_sha=head['snapshot'];previous_book=head['original_workbook']
    if previous_sha:
     reference=self.artifact(e,previous_sha);reference_raw=bounded(reference);reference_book=self.artifact(e,previous_book) if previous_book else None
   elif not events and self.initial_reference:
    reference=self.initial_reference;reference_raw=bounded(reference);previous=invoice_core.validate_cut(engine.load_json_bytes(reference_raw))
    if previous['scope']!=cut['scope']:raise ValueError('Bootstrap reference does not have the declared observation universe')
    reference_book=self.original(previous)
   # A new observation universe starts a separate chain. It does not inherit
   # a fixed bootstrap or fabricate row removals from another period.
   token=engine.sha(engine.canonical({'source':current_sha,'policy':engine.sha(policy_raw),'workbook':original_sha,'reference':engine.sha(reference_raw) if reference_raw else None,'reference_book':engine.file_hash(reference_book) if reference_book else None,'implementation':self.code}))
   if token==self.last_token:
    return {**self.last_result,'reused':True}
  result=invoice_pipeline.execute(self.source,self.policy,self.runtime,reference,original,reference_book,source_bytes=raw,policy_bytes=policy_raw,reference_bytes=reference_raw)
  payload={'series':self.series,'scope_hash':scope_sha,'snapshot':result['snapshot'],'run_id':result['run_id'],'reference_snapshot':engine.sha(reference_raw) if reference_raw else None,'original_workbook':original_sha,'reference_workbook':engine.file_hash(reference_book) if reference_book else None,'token':token}
  with engine.Engine(self.runtime) as e:
   bundle=e.store_object(self.code_bundle)
   e.db.execute('BEGIN IMMEDIATE')
   try:
    latest=next((p for p in self.events(e) if p['scope_hash']==scope_sha),None)
    if not latest or latest.get('token')!=token:
     payload['observer_bundle']=engine.sha(self.code_bundle)
     e.db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?)',(engine.sha(self.code_bundle),str(bundle.relative_to(e.root))))
     e.append('invoice.observer.accepted',payload)
    e.db.execute('COMMIT')
   except Exception:e.db.execute('ROLLBACK');raise
  self.last_token=token;self.last_result=result;self.last_failure=None;return result
 def status(self):
  with engine.Engine(self.runtime) as e:
   events=self.events(e);latest=events[0] if events else None
  return {'pid':os.getpid(),'checked_at':engine.now(),'mode':'invoice_file_observer','last_accepted':latest}
 def poll(self):
  health={'pid':os.getpid(),'checked_at':engine.now(),'mode':'invoice_file_observer','status':'checking'}
  try:
   result=self.step();self.last_failure=None;health.update(status='healthy',run_id=result['run_id'],snapshot=result['snapshot'],reference_snapshot=self.last_result and self.status()['last_accepted'].get('reference_snapshot'),coverage=result['coverage'],reused=result['reused'])
  except Exception as error:
   health.update(status='degraded',error_type=type(error).__name__,reason=str(error))
   token=engine.sha(engine.canonical({'source':engine.file_hash(self.source),'policy':engine.file_hash(self.policy),'code':implementation(),'error':type(error).__name__,'message':str(error)}))
   try:
    with engine.Engine(self.runtime) as e:
     head=next(iter(self.events(e)),None);health['last_accepted']=head
     if token!=self.last_failure:
      objects={}
      for name,path in [('source',self.source),('policy',self.policy)]:
       try:
        rejected=bounded(path);obj=e.store_object(rejected);objects[name]={'sha256':engine.sha(rejected),'object_path':str(obj.relative_to(e.root))}
       except OSError:pass
       except ValueError:pass
      # Catalog every retained object so common ledger verification covers
      # both rejected inputs, without treating either as an accepted run.
      e.db.execute('BEGIN IMMEDIATE')
      try:
       for obj in objects.values():e.db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?)',(obj['sha256'],obj['object_path']))
       e.append('invoice.observer.rejected',{'series':self.series,'failure_fingerprint':token,'error_type':type(error).__name__,'retained_inputs':objects});e.db.execute('COMMIT')
      except Exception:e.db.execute('ROLLBACK');raise
    self.last_failure=token
   except Exception as integrity_error:health['integrity_unverified']=True;health['integrity_error_type']=type(integrity_error).__name__
  self.runtime.mkdir(parents=True,exist_ok=True);path=self.runtime/'invoice-health.json';temp=path.with_suffix('.tmp');temp.write_text(engine.canonical(health),encoding='utf-8');os.replace(temp,path);return health

def watch(source,policy,runtime,originals,initial_reference=None,interval=10,iterations=None):
 if interval<1:raise ValueError('Minimum poll interval: one second')
 observer=InvoiceObserver(source,policy,runtime,originals,initial_reference)
 with observer_lock(runtime):
  i=0
  while True:
   result=observer.poll();i+=1
   if iterations is not None and i>=iterations:return result
   time.sleep(interval)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--policy',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--originals',type=Path,required=True);p.add_argument('--initial-reference',type=Path);p.add_argument('--interval',type=float,default=10);p.add_argument('--iterations',type=int);a=p.parse_args();print(engine.canonical(watch(a.source,a.policy,a.runtime,a.originals,a.initial_reference,a.interval,a.iterations)))
