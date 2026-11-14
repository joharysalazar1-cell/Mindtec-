"""Continuously prepare coherent local packages; no network transport exists here."""
import argparse,json,os,time
from pathlib import Path
import engine,sync_outbox
from supervisor import exclusive,atomic

class Observer:
 def __init__(self,invoice_runtime,scan_runtime,lineage_runtime,runtime,origin,project_id):
  self.sources=[Path(p).resolve() for p in [invoice_runtime,scan_runtime,lineage_runtime]];self.runtime=Path(runtime).resolve();self.target=sync_outbox.target(origin,project_id)
  if len(set(self.sources))!=3 or any(self.runtime.is_relative_to(p) or p.is_relative_to(self.runtime) for p in self.sources):raise ValueError('Distinct, separate source and outbox custody required')
  self.code={**sync_outbox.LOADED,Path(__file__).name:Path(__file__).read_bytes()};self.bundle=engine.code_bundle(self.code);self.last_token=None;self.last_accepted=None
 def token(self):
  if any(Path(__file__).with_name(n).read_bytes()!=b for n,b in self.code.items()):raise RuntimeError('Outbox observer implementation changed; restart required')
  observed=[]
  for path in self.sources:
   if not (path/'audit.sqlite').is_file():raise ValueError('Source custody not available')
   with engine.Engine(path) as e:
    e.db.execute('BEGIN')
    try:
     head=e.verify();run=e.db.execute('SELECT id,snapshot_hash FROM runs ORDER BY at DESC LIMIT 1').fetchone()
     if not run:raise ValueError('Source has no accepted audit')
     observed.append({'run_id':run['id'],'source_sha256':run['snapshot_hash'],'ledger_head':head})
    finally:e.db.execute('ROLLBACK')
  return engine.sha(engine.canonical({'sources':observed,'target':self.target,'observer_bundle':engine.sha(self.bundle)}))
 def accepted(self):
  if not (self.runtime/'audit.sqlite').is_file():return None
  with engine.Engine(self.runtime) as e:
   e.verify()
   for row in e.db.execute('SELECT id,snapshot_hash,rules_json FROM runs ORDER BY at DESC'):
    if json.loads(row['rules_json']).get('kind')!='sync_outbox':continue
    obj=e.db.execute('SELECT object_path FROM snapshots WHERE hash=?',(row['snapshot_hash'],)).fetchone();manifest=engine.load_json_bytes((e.root/obj[0]).read_bytes())
    if manifest.get('target')==self.target and manifest.get('schema')=='mindtec-sync-package/1' and manifest.get('state')=='prepared_not_sent':return {'run_id':row['id'],'snapshot':row['snapshot_hash'],'state':'prepared_not_sent','artifacts':len(manifest['artifacts'])}
  return None
 def receipt(self,result,token):
  with engine.Engine(self.runtime) as e:
   e.verify();obj=e.store_object(self.bundle);payload={'run_id':result['run_id'],'snapshot':result['snapshot'],'source_token':token,'observer_bundle':engine.sha(self.bundle),'target':self.target,'state':'prepared_not_sent'}
   e.db.execute('BEGIN IMMEDIATE')
   try:
    latest=None
    for row in e.db.execute('SELECT event_json FROM events ORDER BY seq DESC'):
     event=json.loads(row[0])
     if event['action']=='outbox.observer.prepared' and event['payload'].get('target')==self.target:latest=event['payload'];break
    if latest!=payload:
     e.db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?)',(engine.sha(self.bundle),str(obj.relative_to(e.root))));e.append('outbox.observer.prepared',payload)
    e.db.execute('COMMIT')
   except Exception:e.db.execute('ROLLBACK');raise
 def poll(self):
  health={'pid':os.getpid(),'checked_at':engine.now(),'mode':'local_sync_outbox_observer','delivery':'not_configured','outbox_custody_verified':False,'last_accepted':self.last_accepted}
  try:
   # Verify output custody even when the source token is unchanged. Recover the
   # durable accepted package on restart, rather than trusting health.json.
   prior=self.accepted()
   if self.last_accepted and prior is None:raise ValueError('Previously accepted outbox custody is missing')
   health['outbox_custody_verified']=prior is not None
   if self.last_accepted is None:self.last_accepted=prior
   token=self.token()
   if token!=self.last_token:
    result=sync_outbox.prepare(*self.sources,self.runtime,self.target['origin'],self.target['project_id']);self.receipt(result,token);self.last_accepted={k:result[k] for k in ['run_id','snapshot','state','artifacts']};self.last_token=token
   health.update(status='healthy',state='prepared_not_sent',outbox_custody_verified=True,run_id=self.last_accepted['run_id'],last_accepted=self.last_accepted)
  except Exception as error:health.update(status='degraded',error_type=type(error).__name__,reason=str(error),state='prepared_not_sent' if self.last_accepted else 'waiting_first_package',last_accepted=self.last_accepted)
  atomic(self.runtime/'health.json',health);return health

def watch(observer,interval=60,iterations=None):
 if isinstance(interval,bool) or not 30<=interval<=3600:raise ValueError('Outbox interval must be between 30 and 3600 seconds')
 with exclusive(observer.runtime/'outbox-observer.lock'):
  count=0
  while True:
   result=observer.poll();count+=1
   if iterations is not None and count>=iterations:return result
   time.sleep(interval)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--invoice-runtime',required=True,type=Path);p.add_argument('--scan-runtime',required=True,type=Path);p.add_argument('--lineage-runtime',required=True,type=Path);p.add_argument('--runtime',required=True,type=Path);p.add_argument('--origin',required=True);p.add_argument('--project-id',required=True);p.add_argument('--interval',type=float,default=60);p.add_argument('--iterations',type=int);a=p.parse_args();print(engine.canonical(watch(Observer(a.invoice_runtime,a.scan_runtime,a.lineage_runtime,a.runtime,a.origin,a.project_id),a.interval,a.iterations)))
