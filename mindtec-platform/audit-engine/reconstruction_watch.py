"""Observe accepted local PS executions and retain coherent reconstruction cycles, without network."""
import argparse,base64,os,time
from pathlib import Path
import engine,collection_watch,supervisor,reconstruction_cycle as cycle

LOADED=Path(__file__).read_bytes()


class Observer:
 def __init__(self,profile_path):
  self.path=Path(profile_path).resolve();q,_,_=cycle.profile(self.path);self.runtime=Path(q['runtime']).resolve();self.source=Path(q['ps_runtime']).resolve();self.reports=Path(q['report_dir']).resolve();self.series=engine.sha(str(self.path));self.last_accepted=None
 def slim(self,prior):
  if prior is None:return None
  return {'run_id':prior['run_id'],'snapshot_sha256':prior['snapshot_sha256'],'context_sha256':prior['result']['context_sha256'],'report':prior['result']['report']}
 def poll(self):
  h={'schema':'mindtec-reconstruction-observer-health/1','pid':os.getpid(),'checked_at':engine.now(),'observer_implementation_sha256':engine.sha(LOADED),'network_delivery':False,'custody_verified':False,'last_accepted':self.last_accepted};raw=None
  try:
   prior=cycle.verified(self.runtime)
   if prior is not None and prior['result']['series']!=self.series:raise ValueError('Cycle runtime belongs to another observer profile')
   self.last_accepted=self.slim(prior)
   if Path(__file__).read_bytes()!=LOADED:raise ValueError('Reconstruction observer implementation changed; restart before accepting')
   q,raw,_=cycle.profile(self.path)
   if any(Path(q[k]).resolve()!=v for k,v in [('runtime',self.runtime),('ps_runtime',self.source),('report_dir',self.reports)]):raise ValueError('Observer source, custody or report directory changed')
   accepted=cycle.execute(self.path);verified=cycle.verified(self.runtime,accepted['run_id'])
   if Path(__file__).read_bytes()!=LOADED:raise ValueError('Observer implementation changed during cycle verification')
   if verified is None:raise ValueError('Reconstruction cycle was not retained')
   self.last_accepted=self.slim(verified);h.update(status='healthy',state='verified_unchanged' if accepted['reused'] else 'new_cycle_accepted',custody_verified=True,run_id=accepted['run_id'],report_path=accepted['report']['path'],completed_stages=len(verified['result']['stages']),last_accepted=self.last_accepted)
  except Exception as error:
   h.update(status='degraded',state='last_valid_cycle_preserved' if self.last_accepted else 'no_cycle_accepted',reason=str(error)[:2000],error_type=type(error).__name__,last_accepted=self.last_accepted)
   try:
    if raw is None:raw=collection_watch.bounded(self.path,100000)
    envelope=engine.canonical({'encoding':'base64','original_sha256':engine.sha(raw),'content':base64.b64encode(raw).decode()}).encode();payload={'series':self.series,'error_type':type(error).__name__,'reason':str(error)[:2000],'profile_sha256':engine.sha(raw),'last_accepted':self.last_accepted,'profile_object_sha256':engine.sha(envelope)}
    with engine.Engine(self.runtime) as e:
     e.verify();last=e.db.execute('SELECT event_json FROM events ORDER BY seq DESC LIMIT 1').fetchone()
     if last is None or engine.load_json_bytes(last[0].encode()).get('payload')!=payload:
      e.db.execute('BEGIN IMMEDIATE')
      try:
       obj=e.store_object(envelope,'.json');e.db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?)',(engine.sha(envelope),str(obj.relative_to(e.root))));e.append('reconstruction.observer.rejected',payload);e.db.execute('COMMIT')
      except Exception:e.db.execute('ROLLBACK');raise
   except Exception:h['failure_history_unverified']=True
  h['checked_at']=engine.now();supervisor.atomic(self.runtime/'health.json',h);return h


def watch(observer,interval=60,iterations=None):
 if isinstance(interval,bool) or not isinstance(interval,(int,float)) or not 60<=interval<=3600:raise ValueError('Reconstruction interval must be 60 to 3600 seconds')
 if iterations is not None and (type(iterations) is not int or iterations<1):raise ValueError('Positive bounded iteration count required')
 with supervisor.exclusive(observer.runtime/'reconstruction-observer.lock'):
  count=0;h=None
  try:
   while True:
    h=observer.poll();count+=1
    if iterations is not None and count>=iterations:return h
    time.sleep(interval)
  finally:
   if h is not None:
    h.update(last_poll_status=h['status'],last_poll_state=h.get('state'),status='stopped',state='observer_stopped',observer_running=False,checked_at=engine.now());supervisor.atomic(observer.runtime/'health.json',h)


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',required=True,type=Path);p.add_argument('--interval',type=float,default=60);p.add_argument('--iterations',type=int);a=p.parse_args();print(engine.canonical(watch(Observer(a.profile),a.interval,a.iterations)))
