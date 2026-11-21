"""Publish new prepared packages; periodic readback never masquerades as live data."""
import argparse,json,os,time
from pathlib import Path
import engine,sync_client
from supervisor import exclusive,atomic

class Observer:
 def __init__(self,config,interval=300,recheck_interval=3600,*,transport=None,credential_provider=None,clock=time.monotonic):
  if isinstance(interval,bool) or not isinstance(interval,(int,float)) or not 60<=interval<=3600:raise ValueError('Delivery interval must be 60 to 3600 seconds')
  if isinstance(recheck_interval,bool) or not isinstance(recheck_interval,(int,float)) or not interval<=recheck_interval<=86400:raise ValueError('Remote recheck interval must be between delivery interval and 86400 seconds')
  self.path=Path(config);self.c,self.raw=sync_client.config_file(self.path);self.runtime=Path(self.c['runtime']);self.interval=interval;self.recheck_interval=recheck_interval;self.transport=transport;self.provider=credential_provider or (lambda c:os.environ.get(c['token_env']));self.clock=clock;self.last_token=None;self.last_remote_check=None;self.last_remote_check_at=None;self.last_accepted=None;self.failures=0;self.retry_at=0
  self.code={**sync_client.LOADED,Path(__file__).name:Path(__file__).read_bytes()};self.bundle=engine.code_bundle(self.code)
 def accepted(self):
  if not (self.runtime/'audit.sqlite').is_file():return None
  with engine.Engine(self.runtime) as e:
   e.verify()
   for row in e.db.execute('SELECT * FROM runs ORDER BY at DESC'):
    rules=json.loads(row['rules_json'])
    if rules.get('kind')!='sync_delivery' or rules.get('origin')!=self.c['origin']:continue
    ref=e.db.execute('SELECT object_path FROM snapshots WHERE hash=?',(row['snapshot_hash'],)).fetchone();a=sync_client.parsed((e.root/ref[0]).read_bytes())
    sync_client.require(a.get('schema')=='mindtec-sync-acknowledgment/1' and a.get('state')=='delivered_verified','delivery_acknowledgment_contract')
    if a.get('project_id')!=self.c['project_id']:continue
    sync_client.require(a.get('local_package_run_id')==rules.get('local_package_run_id') and all(isinstance(a.get(k),str) and sync_client.HEX.fullmatch(a[k]) for k in ['remote_receipt_id','remote_receipt_sha256','local_manifest_sha256']),'delivery_acknowledgment_contract')
    return {'run_id':row['id'],'local_package_run_id':a['local_package_run_id'],'remote_receipt_id':a['remote_receipt_id'],'accepted_at':row['at']}
  return None
 def record(self,action,payload):
  with engine.Engine(self.runtime) as e:
   e.verify();bundle=e.store_object(self.bundle);data={**payload,'observer_bundle':engine.sha(self.bundle),'config_sha256':engine.sha(self.raw)}
   previous=None
   for row in e.db.execute('SELECT event_json FROM events ORDER BY seq DESC'):
    event=json.loads(row[0])
    if event['action'].startswith('sync.publisher.'):previous=event;break
   e.db.execute('BEGIN IMMEDIATE')
   try:
    if not previous or previous['action']!=action or previous['payload']!=data:
     e.db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?)',(engine.sha(self.bundle),str(bundle.relative_to(e.root))));e.append(action,data)
    e.db.execute('COMMIT')
   except Exception:e.db.execute('ROLLBACK');raise
 def poll(self):
  h={'pid':os.getpid(),'checked_at':engine.now(),'mode':'local_sync_delivery_observer','remote_verified_this_poll':False,'local_delivery_custody_verified':False,'last_accepted':self.last_accepted,'last_remote_check_at':self.last_remote_check_at}
  try:
   sync_client.require(self.path.read_bytes()==self.raw,'configuration_changed_restart_required');sync_client.require(all(Path(__file__).with_name(n).read_bytes()==b for n,b in self.code.items()),'implementation_changed_restart_required')
   previous=self.accepted()
   if self.last_accepted and previous is None:raise sync_client.SyncError('previous_delivery_custody_missing')
   self.last_accepted=previous;h['local_delivery_custody_verified']=previous is not None
   if not self.c['enabled']:h.update(status='disabled',state='delivery_not_enabled',last_accepted=previous);atomic(self.runtime/'health.json',h);return h
   client=sync_client.Client(self.path,transport=self.transport);package=client.capture();token=package['run']['id'];now=self.clock()
   if now<self.retry_at:h.update(status='degraded',state='waiting_retry',retry_in_seconds=round(self.retry_at-now,1),last_accepted=previous,run_id=previous['run_id'] if previous else None);atomic(self.runtime/'health.json',h);return h
   credential=self.provider(self.c);sync_client.require(isinstance(credential,str) and 0<len(credential)<=10000 and all(33<=ord(c)<=126 for c in credential),'managed_service_credential_missing_or_invalid')
   unchanged=previous and previous['local_package_run_id']==token and self.last_token==token
   if unchanged and self.last_remote_check is not None and now-self.last_remote_check<self.recheck_interval:
    h.update(status='healthy',state='unchanged_package_local_receipt_verified',last_accepted=previous,run_id=previous['run_id'],next_remote_recheck_seconds=round(self.recheck_interval-(now-self.last_remote_check),1));atomic(self.runtime/'health.json',h);return h
   client.token=credential;result=client.run();credential=None
   if result['status']!='healthy':raise sync_client.SyncError(result.get('reason','delivery_failed'),result.get('http_status'),result.get('retry_after_seconds'))
   self.last_accepted=self.accepted();sync_client.require(self.last_accepted and self.last_accepted['local_package_run_id']==token,'delivery_receipt_not_retained')
   self.record('sync.publisher.confirmed',{'local_package_run_id':token,'delivery_run_id':result['run_id'],'remote_receipt_id':result['remote_receipt_id']})
   self.last_token=token;self.last_remote_check=self.clock();self.last_remote_check_at=engine.now();self.failures=0;self.retry_at=0
   h.update(status='healthy',state='delivered_verified',run_id=result['run_id'],remote_verified_this_poll=True,local_delivery_custody_verified=True,last_remote_check_at=self.last_remote_check_at,last_accepted=self.last_accepted)
  except Exception as error:
   reason=error.reason if isinstance(error,sync_client.SyncError) else 'local_validation_or_storage_failure';self.failures+=1;delay=max(min(3600,self.interval*2**min(self.failures-1,6)),getattr(error,'retry_after',None) or 0);self.retry_at=self.clock()+delay
   h.update(status='degraded',state='delivery_not_confirmed',reason=reason,error_type=type(error).__name__,http_status=getattr(error,'status',None),retry_in_seconds=delay,last_accepted=self.last_accepted)
   try:self.record('sync.publisher.failed',{'reason':reason,'http_status':getattr(error,'status',None),'last_delivery_run_id':self.last_accepted['run_id'] if self.last_accepted else None})
   except Exception:h['failure_history_unverified']=True
  atomic(self.runtime/'health.json',h);return h

def watch(observer,iterations=None):
 with exclusive(observer.runtime/'sync-publisher.lock'):
  count=0
  while True:
   result=observer.poll();count+=1
   if iterations is not None and count>=iterations:return result
   time.sleep(observer.interval)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',required=True,type=Path);p.add_argument('--interval',type=float,default=300);p.add_argument('--recheck-interval',type=float,default=3600);p.add_argument('--iterations',type=int);a=p.parse_args();print(engine.canonical(watch(Observer(a.config,a.interval,a.recheck_interval),a.iterations)))
