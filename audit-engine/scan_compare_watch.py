"""Watch accepted Scan custody; preserve a baseline and monthly comparison batches."""
import argparse,json,os,time
from pathlib import Path
import engine,scan_compare,supervisor,windows_job

LOADED={'engine.py':engine.IMPLEMENTATION_BYTES,'scan_compare.py':scan_compare.IMPLEMENTATION_BYTES,'supervisor.py':supervisor.IMPLEMENTATION_BYTES,'windows_job.py':Path(windows_job.__file__).read_bytes(),Path(__file__).name:Path(__file__).read_bytes()}

def object_bytes(e,digest):
 row=e.db.execute('SELECT object_path FROM snapshots WHERE hash=?',(digest,)).fetchone()
 if not row:raise ValueError('Referenced object missing')
 raw=(e.root/row[0]).read_bytes()
 if engine.sha(raw)!=digest:raise ValueError('Referenced object integrity failure')
 return raw

class Observer:
 def __init__(self,scan_runtime,runtime,months):
  self.source=Path(scan_runtime).resolve();self.runtime=Path(runtime).resolve();self.months=scan_compare.months_contract(months)
  if self.source.is_relative_to(self.runtime) or self.runtime.is_relative_to(self.source):raise ValueError('Comparison custody must be separate from Scan')
  self.series=engine.sha(engine.canonical({'scan_runtime':str(self.source),'months':self.months}));self.bundle=engine.code_bundle(LOADED);self.last_accepted=None
 def current(self):
  if not (self.source/'audit.sqlite').is_file():raise ValueError('Scan custody unavailable')
  with engine.Engine(self.source) as e:
   e.db.execute('BEGIN')
   try:
    e.verify()
    for row in e.db.execute('SELECT * FROM runs ORDER BY at DESC'):
     rules=json.loads(row['rules_json'])
     if rules.get('kind') is not None or not rules.get('engine_version') or not isinstance(rules.get('rules'),dict):continue
     raw=object_bytes(e,row['snapshot_hash']);engine.validate_scan(engine.load_json_bytes(raw))
     implementation=rules.get('reference_sources',{}).get('implementation_bundle')
     if not implementation:raise ValueError('Accepted Scan implementation evidence missing')
     return {'source':raw,'record':engine.canonical(dict(row)).encode(),'implementation':object_bytes(e,implementation),'run_id':row['id'],'snapshot':row['snapshot_hash']}
    raise ValueError('No accepted Scan run')
   finally:e.db.execute('ROLLBACK')
 def prior(self):
  if not (self.runtime/'audit.sqlite').is_file():return None
  with engine.Engine(self.runtime) as e:
   e.verify()
   for row in e.db.execute('SELECT event_json FROM events ORDER BY seq DESC'):
    event=json.loads(row[0])
    if event['action']!='scan.comparison.accepted':continue
    payload=event['payload']
    if payload.get('series')!=self.series:raise ValueError('Comparison runtime bound to another source or month scope')
    run=e.db.execute('SELECT * FROM runs WHERE id=?',(payload['run_id'],)).fetchone()
    if not run:raise ValueError('Comparison acceptance run missing')
    rules=json.loads(run['rules_json']);refs=rules['reference_sources'];result=engine.load_json_bytes(object_bytes(e,run['snapshot_hash']))
    if rules.get('kind')!='scan_comparison_observer' or rules.get('series')!=self.series or refs['current_scan_source']!=payload['source_snapshot'] or result['current_source_sha256']!=payload['source_snapshot'] or result['state']!=payload['state']:raise ValueError('Comparison acceptance contract differs')
    record=object_bytes(e,refs['current_scan_run']);scan_record=engine.load_json_bytes(record)
    if scan_record['snapshot_hash']!=payload['source_snapshot'] or scan_record['id']!=payload['scan_run_id']:raise ValueError('Comparison Scan binding differs')
    return {**payload,'source':object_bytes(e,refs['current_scan_source']),'record':record,'implementation':object_bytes(e,refs['current_scan_implementation'])}
  return None
 def slim(self,prior):return {k:prior[k] for k in ['run_id','state','source_snapshot','scan_run_id']} if prior else None
 def accept(self,current,prior):
  data=engine.load_json_bytes(current['source']);baseline=prior is None
  # Validate coverage even for the first baseline. No invented before-values.
  previous=data if baseline else engine.load_json_bytes(prior['source'])
  combined=scan_compare.compare([previous],[data],self.months)
  monthly={} if baseline else {m:scan_compare.compare([previous],[data],[m]) for m in self.months}
  result={'schema':'mindtec-scan-comparison-batch/1','state':'baseline_only' if baseline else 'comparison_available','months':self.months,'current_source_sha256':current['snapshot'],'previous_source_sha256':None if baseline else prior['source_snapshot'],'baseline_counts':{m:counts['current'] for m,counts in combined['summary']['months'].items()} if baseline else None,'combined':None if baseline else combined,'monthly':monthly,'limits':['Baseline is not a comparison with a prior cut.','Monthly and combined signals overlap; do not sum them as independent errors.','No source, KPI, exclusion or human decision modified.','No network download or delivery.']}
  refs={'current_scan_source':(current['source'],'.json'),'current_scan_run':(current['record'],'.json'),'current_scan_implementation':(current['implementation'],'.json'),'observer_implementation':(self.bundle,'.json')}
  if prior:refs.update({'previous_scan_source':(prior['source'],'.json'),'previous_scan_run':(prior['record'],'.json'),'previous_scan_implementation':(prior['implementation'],'.json')})
  policy={'schema':'mindtec-scan-comparison-observer-policy/1','version':'1','months':self.months,'series':self.series,'source_mutation':False}
  rules={'kind':'scan_comparison_observer','version':'1','series':self.series,'reference_sources':{k:engine.sha(v[0]) for k,v in refs.items()}}
  with engine.Engine(self.runtime) as e:
   accepted=e.record_result(engine.canonical(result).encode(),policy,rules,[] if baseline else combined['findings'],{'state':result['state'],'months':self.months},refs)
   payload={'series':self.series,'run_id':accepted['run_id'],'state':result['state'],'source_snapshot':current['snapshot'],'scan_run_id':current['run_id']}
   e.db.execute('BEGIN IMMEDIATE')
   try:e.append('scan.comparison.accepted',payload);e.db.execute('COMMIT')
   except Exception:e.db.execute('ROLLBACK');raise
  return self.prior()
 def failure(self,error,current):
  with engine.Engine(self.runtime) as e:
   e.verify();refs={'observer_implementation':self.bundle}
   if current:refs.update({'candidate_scan_source':current['source'],'candidate_scan_run':current['record'],'candidate_scan_implementation':current['implementation']})
   payload={'series':self.series,'reason':str(error),'error_type':type(error).__name__,'artifacts':{k:engine.sha(v) for k,v in refs.items()},'last_accepted':self.last_accepted}
   previous=e.db.execute('SELECT event_json FROM events ORDER BY seq DESC LIMIT 1').fetchone();previous=json.loads(previous[0]) if previous else None
   if previous and previous['action']=='scan.comparison.rejected' and previous['payload']==payload:return
   e.db.execute('BEGIN IMMEDIATE')
   try:
    for raw in refs.values():
     obj=e.store_object(raw);e.db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?)',(engine.sha(raw),str(obj.relative_to(e.root))))
    e.append('scan.comparison.rejected',payload);e.db.execute('COMMIT')
   except Exception:e.db.execute('ROLLBACK');raise
 def poll(self):
  h={'pid':os.getpid(),'checked_at':engine.now(),'mode':'accepted_scan_comparison_observer','comparison_custody_verified':False,'last_accepted':self.last_accepted};current=None
  try:
   if any(Path(__file__).with_name(n).read_bytes()!=raw for n,raw in LOADED.items()):raise ValueError('Implementation changed; restart comparison observer')
   prior=self.prior()
   if self.last_accepted and not prior:raise ValueError('Previously accepted comparison missing')
   self.last_accepted=self.slim(prior);h['comparison_custody_verified']=prior is not None
   current=self.current()
   if not prior or current['snapshot']!=prior['source_snapshot']:prior=self.accept(current,prior)
   self.last_accepted=self.slim(prior)
   h.update(status='healthy',state=prior['state'],comparison_custody_verified=True,run_id=prior['run_id'],last_accepted=self.last_accepted,observed_scan_run_id=current['run_id'])
  except Exception as error:
   h.update(status='degraded',state='comparison_not_updated',error_type=type(error).__name__,reason=str(error),last_accepted=self.last_accepted)
   try:self.failure(error,current)
   except Exception:h['failure_history_unverified']=True
  supervisor.atomic(self.runtime/'health.json',h);return h

def watch(observer,interval=30,iterations=None):
 if isinstance(interval,bool) or not isinstance(interval,(int,float)) or not 10<=interval<=3600:raise ValueError('Comparison interval must be 10 to 3600 seconds')
 with supervisor.exclusive(observer.runtime/'scan-comparison.lock'):
  count=0
  while True:
   result=observer.poll();count+=1
   if iterations is not None and count>=iterations:return result
   time.sleep(interval)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--scan-runtime',required=True,type=Path);p.add_argument('--runtime',required=True,type=Path);p.add_argument('--months',required=True,nargs='+');p.add_argument('--interval',type=float,default=30);p.add_argument('--iterations',type=int);a=p.parse_args();print(engine.canonical(watch(Observer(a.scan_runtime,a.runtime,a.months),a.interval,a.iterations)))
