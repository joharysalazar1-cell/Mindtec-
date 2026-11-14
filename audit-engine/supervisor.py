"""Own and supervise local observers; never kill a PID found in a state file."""
import argparse,contextlib,datetime as dt,hashlib,json,os,subprocess,sys,time
from pathlib import Path
import windows_job

ROOT=Path(__file__).resolve().parent
IMPLEMENTATION_BYTES=Path(__file__).read_bytes()
JOB_FIELDS={'scan':['source','policy','runtime'],'invoice':['source','policy','runtime','originals'],'lineage':['invoice_runtime','scan_runtime','kpi_dir','perfect_store_dir','runtime','report'],'feed':['config','runtime']}
JOB_SCRIPTS={'scan':'engine.py','invoice':'invoice_watch.py','lineage':'lineage_watch.py','feed':'scan_feed.py'}
def canonical(v):return json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':'))
def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def atomic(path,value):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp');temp.write_text(canonical(value),encoding='utf-8');os.replace(temp,path)

@contextlib.contextmanager
def exclusive(path):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);f=path.open('a+b');locked=False
 if f.seek(0,2)==0:f.write(b'0');f.flush()
 f.seek(0)
 try:
  try:
   if os.name=='nt':
    import msvcrt
    msvcrt.locking(f.fileno(),msvcrt.LK_NBLCK,1)
   else:
    import fcntl
    fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)
   locked=True
  except OSError as e:raise RuntimeError('Another supervisor owns this runtime') from e
  yield
 finally:
  if locked:
   f.seek(0)
   if os.name=='nt':msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
   else:fcntl.flock(f,fcntl.LOCK_UN)
  f.close()

def config_file(path):
 raw=Path(path).read_bytes()
 if len(raw)>100000:raise ValueError('Supervisor configuration exceeds limit')
 config=json.loads(raw)
 if config.get('schema')!='mindtec-supervisor/1' or not isinstance(config.get('jobs'),list) or not config['jobs']:raise ValueError('Supervisor contract required')
 names=set();runtimes=set();feeds=[]
 for job in config['jobs']:
  if not isinstance(job,dict) or not isinstance(job.get('kind'),str) or job['kind'] not in JOB_FIELDS or not isinstance(job.get('name'),str) or not job['name'].strip() or job['name'] in names:raise ValueError('Unique named supported observer jobs required')
  names.add(job['name'])
  for field in JOB_FIELDS[job['kind']]:
   if not isinstance(job.get(field),str) or not Path(job[field]).is_absolute():raise ValueError('Absolute job paths required: '+field)
  root=Path(job['runtime']).resolve()
  if root in runtimes:raise ValueError('Each supervised job requires a distinct runtime')
  runtimes.add(root)
  interval=job.get('interval',10)
  if isinstance(interval,bool) or not isinstance(interval,(int,float)) or not 1<=interval<=(86400 if job['kind']=='feed' else 3600):raise ValueError('Observer interval outside bounds')
  if job['kind']=='feed':
   # Validation reads configuration only: no credential, request or child process.
   from scan_feed import config_file as feed_config
   feed,_=feed_config(job['config'])
   if not feed['enabled']:raise ValueError('Disabled feed cannot be registered as an active supervisor job')
   if Path(feed['runtime']).resolve()!=root or interval!=feed['interval']:raise ValueError('Feed runtime and interval must match its configuration')
   feeds.append(feed)
  if job.get('initial_reference') and not Path(job['initial_reference']).is_absolute():raise ValueError('Absolute bootstrap path required')
 targets=set()
 for feed in feeds:
  target=Path(feed['audit_runtime']).resolve()
  if target in targets:raise ValueError('Only one feed may publish to a Scan runtime')
  targets.add(target)
  matches=[j for j in config['jobs'] if j['kind']=='scan' and Path(j['runtime']).resolve()==target and Path(j['source']).resolve()==Path(feed['destination']).resolve() and Path(j['policy']).resolve()==Path(feed['policy']).resolve()]
  if len(matches)!=1:raise ValueError('Feed must bind to one configured Scan observer with identical source and policy')
 return config,hashlib.sha256(raw).hexdigest()

def command(job):
 if job.get('kind') not in JOB_FIELDS:raise ValueError('Unsupported observer kind')
 args=[sys.executable,str(ROOT/JOB_SCRIPTS[job['kind']])]
 if job['kind']=='feed':return args+['--config',job['config']]
 if job['kind']=='scan':args+=['watch']
 for flag in JOB_FIELDS[job['kind']]:args+=['--'+flag.replace('_','-'),job[flag]]
 if job['kind']=='invoice' and job.get('initial_reference'):args+=['--initial-reference',job['initial_reference']]
 return args+['--interval',str(job.get('interval',10))]

def health(job,pid,clock=None):
 path=Path(job['runtime'])/('invoice-health.json' if job['kind']=='invoice' else 'health.json')
 try:
  with path.open('rb') as f:raw=f.read(100001)
  if len(raw)>100000:raise ValueError('oversized health')
  h=json.loads(raw);timestamp=dt.datetime.fromisoformat(h['checked_at'])
  if timestamp.tzinfo is None:raise ValueError('timestamp timezone required')
  age=((clock or dt.datetime.now(dt.timezone.utc))-timestamp).total_seconds()
  if h.get('pid')!=pid:return {'status':'awaiting_owned_health','reason':'health_belongs_to_another_process'}
  if age< -5 or age>max(30,job.get('interval',10)*4):return {'status':'degraded','reason':'heartbeat_outside_window','age_seconds':round(age,1)}
  # Health never authorizes termination. Only Popen.poll establishes an exit.
  return {'status':h.get('status','unknown'),'checked_at':h['checked_at'],'age_seconds':round(age,1),'run_id':h.get('run_id') or (h.get('last_success') or {}).get('run_id'),'error_type':h.get('error_type'),**({'reason':h.get('reason'),'http_status':h.get('http_status')} if job['kind']=='feed' else {})}
 except (OSError,ValueError,KeyError,TypeError):return {'status':'awaiting_owned_health','reason':'unreadable_health'}

class Supervisor:
 def __init__(self,jobs,runtime,*,spawn=None,monotonic=time.monotonic):
  self.jobs=jobs;self.root=Path(runtime);self.root.mkdir(parents=True,exist_ok=True);self.spawn=spawn or subprocess.Popen;self.clock=monotonic;self.children={};self.state={j['name']:{'restarts':0,'next_start':0,'failures':0} for j in jobs};self.head='GENESIS'
  self.log=self.root/'events.jsonl'
  if self.log.exists():
   for line in self.log.read_text(encoding='utf-8').splitlines():
    item=json.loads(line);event=item['event']
    if event['previous']!=self.head or hashlib.sha256(canonical(event).encode()).hexdigest()!=item['hash']:raise ValueError('Supervisor event chain integrity failed')
    for reference in event.get('payload',{}).get('artifacts',{}).values():
     target=(self.root/reference['path']).resolve();target.relative_to(self.root.resolve())
     if hashlib.sha256(target.read_bytes()).hexdigest()!=reference['sha256']:raise ValueError('Supervisor artifact integrity failed')
    self.head=item['hash']
 def archive(self,raw,extension):
  hash_=hashlib.sha256(raw).hexdigest();folder=self.root/'objects';folder.mkdir(exist_ok=True);path=folder/(hash_+extension)
  try:
   with path.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
  except FileExistsError:
   if path.read_bytes()!=raw:raise ValueError('Supervisor artifact integrity failed')
  return {'sha256':hash_,'path':str(path.relative_to(self.root))}
 def event(self,action,payload):
  e={'at':now(),'action':action,'payload':payload,'previous':self.head};hash_=hashlib.sha256(canonical(e).encode()).hexdigest()
  with self.log.open('a',encoding='utf-8') as f:f.write(canonical({'event':e,'hash':hash_})+'\n');f.flush();os.fsync(f.fileno())
  self.head=hash_
 def tick(self):
  current=self.clock();out=[]
  for job in self.jobs:
   name=job['name'];state=self.state[name];child=self.children.get(name)
   if child is not None:
    code=child.poll()
    if code is not None:
     self.event('observer.exited',{'job':name,'pid':child.pid,'return_code':code});self.children.pop(name);child=None;state['failures']+=1;state['next_start']=current+min(300,5*2**min(state['failures']-1,6));state['last_return_code']=code
   if child is None and current>=state['next_start']:
    try:
     child=self.spawn(command(job),cwd=str(ROOT),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
     self.children[name]=child;state['restarts']+=1;state['started']=current;self.event('observer.started',{'job':name,'pid':child.pid,'attempt':state['restarts']})
    except OSError as error:
     state['failures']+=1;state['next_start']=current+min(300,5*2**min(state['failures']-1,6));self.event('observer.start_failed',{'job':name,'error_type':type(error).__name__})
   if child is not None:
    observed=health(job,child.pid)
    if observed['status']=='healthy' and current-state['started']>=60:state['failures']=0
    out.append({'name':name,'pid':child.pid,'process':'running','starts':state['restarts'],**observed})
   else:out.append({'name':name,'process':'exited','status':'backoff','retry_in_seconds':max(0,round(state['next_start']-current,1)),'return_code':state.get('last_return_code')})
  return out
 def close(self):
  # Popen handles belong exclusively to this supervisor, never loaded from JSON.
  for name,child in self.children.items():
   if child.poll() is None:
    child.terminate()
    try:child.wait(timeout=10)
    except subprocess.TimeoutExpired:child.kill();child.wait(timeout=10)
   self.event('observer.stopped',{'job':name,'pid':child.pid,'return_code':child.poll()})
  self.children.clear()

def run(config_path,runtime,interval=2):
 config,config_hash=config_file(config_path);root=Path(runtime)
 if interval<1:raise ValueError('Minimum supervisor interval: one second')
 with exclusive(root/'supervisor.lock'):
  if (root/'stop.request').exists():
   atomic(root/'supervisor-health.json',{'schema':'mindtec-supervisor-health/1','pid':os.getpid(),'checked_at':now(),'status':'stopped','jobs':[],'stop_requested':True});return
  protection=windows_job.protect_current_process()
  supervisor=Supervisor(config['jobs'],root);config_raw=Path(config_path).read_bytes()
  if hashlib.sha256(config_raw).hexdigest()!=config_hash:raise ValueError('Configuration changed during startup')
  artifacts={'configuration':supervisor.archive(config_raw,'.json'),'implementation':supervisor.archive(IMPLEMENTATION_BYTES,'.py'),'windows_job':supervisor.archive(Path(windows_job.__file__).read_bytes(),'.py')}
  supervisor.event('supervisor.started',{'pid':os.getpid(),'config_sha256':config_hash,'artifacts':artifacts,'process_protection':protection});state={}
  try:
   while not (root/'stop.request').exists():
    jobs=supervisor.tick();state={'schema':'mindtec-supervisor-health/1','pid':os.getpid(),'checked_at':now(),'status':'healthy' if all(j['status']=='healthy' for j in jobs) else 'degraded','config_sha256':config_hash,'jobs':jobs,'event_head':supervisor.head,'process_protection':protection};atomic(root/'supervisor-health.json',state);time.sleep(interval)
  finally:
   supervisor.close();supervisor.event('supervisor.stopped',{'pid':os.getpid()});atomic(root/'supervisor-health.json',{**state,'pid':os.getpid(),'checked_at':now(),'status':'stopped','jobs':[],'event_head':supervisor.head})

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',required=True,type=Path);p.add_argument('--runtime',required=True,type=Path);p.add_argument('--interval',type=float,default=2);a=p.parse_args();run(a.config,a.runtime,a.interval)
