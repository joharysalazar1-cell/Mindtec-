"""Read-only HTTPS ingestion; never reuse browser cookies or persist credentials."""
import argparse,json,os,re,ssl,tempfile,time,urllib.error,urllib.parse,urllib.request
from pathlib import Path
import engine
import supervisor as operations
import windows_job
from supervisor import atomic,exclusive

LOADED={'engine.py':engine.IMPLEMENTATION_BYTES,'supervisor.py':operations.IMPLEMENTATION_BYTES,'windows_job.py':Path(windows_job.__file__).read_bytes(),Path(__file__).name:Path(__file__).read_bytes()}
class FeedError(Exception):
 def __init__(self,reason,http_status=None):super().__init__(reason);self.reason=reason;self.http_status=http_status

def strict_json(raw):
 def pairs(items):
  result={}
  for key,value in items:
   if key in result:raise ValueError('duplicate_json_key')
   result[key]=value
  return result
 def nonfinite(value):raise ValueError('nonfinite_json_number')
 return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=nonfinite)

def config_file(path):
 with Path(path).open('rb') as f:raw=f.read(100001)
 if len(raw)>100000:raise FeedError('config_size_limit')
 try:c=strict_json(raw)
 except (ValueError,UnicodeError):raise FeedError('invalid_config_json') from None
 allowed={'schema','enabled','url','destination','policy','audit_runtime','runtime','auth','timeout','max_seconds','max_bytes','interval'}
 if not isinstance(c,dict) or set(c)-allowed or c.get('schema')!='mindtec-scan-feed/1' or not isinstance(c.get('enabled'),bool):raise FeedError('invalid_config_contract')
 try:
  url=urllib.parse.urlsplit(c.get('url',''));valid=url.scheme=='https' and url.hostname and not url.username and not url.password and not url.query and not url.fragment and url.path.startswith('/') and url.port in (None,443)
 except (ValueError,TypeError):valid=False
 if not valid:raise FeedError('https_endpoint_without_credentials_required')
 for field in ['destination','policy','audit_runtime','runtime']:
  if not isinstance(c.get(field),str) or not Path(c[field]).is_absolute():raise FeedError('absolute_paths_required')
 destination=Path(c['destination']).resolve();audit_root=Path(c['audit_runtime']).resolve();feed_root=Path(c['runtime']).resolve()
 if destination.suffix.lower()!='.json' or destination==Path(c['policy']).resolve() or audit_root==feed_root or destination.is_relative_to(audit_root) or destination.is_relative_to(feed_root):raise FeedError('separate_inbox_policy_and_custody_paths_required')
 auth=c.get('auth')
 if not isinstance(auth,dict) or set(auth)-{'kind','token_env'} or auth.get('kind') not in ['none','bearer_env']:raise FeedError('unsupported_auth_configuration')
 if auth['kind']=='bearer_env' and (not isinstance(auth.get('token_env'),str) or not re.fullmatch(r'MINDTEC_[A-Z0-9_]{1,80}',auth['token_env'])):raise FeedError('dedicated_credential_variable_required')
 for name,low,high in [('timeout',1,30),('max_seconds',1,120),('max_bytes',1,100000000),('interval',30,86400)]:
  if isinstance(c.get(name),bool) or not isinstance(c.get(name),int) or not low<=c[name]<=high:raise FeedError('invalid_download_limits')
 return c,raw

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,request,fp,code,msg,headers,newurl):
  if fp is not None:fp.close()
  raise FeedError('redirect_rejected',code)

def credential(auth,environ):
 if auth['kind']=='none':return None
 token=environ.get(auth['token_env'])
 if not token:raise FeedError('service_credential_missing')
 if len(token)>8000 or any(ord(c)<33 or ord(c)>126 for c in token):raise FeedError('invalid_service_credential')
 return token

def download(config,etag=None,*,environ=None,opener=None,clock=time.monotonic):
 token=credential(config['auth'],os.environ if environ is None else environ)
 headers={'Accept':'application/json','Accept-Encoding':'identity','User-Agent':'MindTEC-read-only-audit/1'}
 if token:headers['Authorization']='Bearer '+token
 if etag and len(etag)<=512 and not any(ord(c)<32 or ord(c)>126 for c in etag):headers['If-None-Match']=etag
 request=urllib.request.Request(config['url'],headers=headers,method='GET')
 client=opener or urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context()))
 started=clock()
 try:
  try:response=client.open(request,timeout=config['timeout'])
  except urllib.error.HTTPError as error:
   code=error.code;error.close()
   if code==304 and etag:return {'not_modified':True,'etag':etag}
   raise FeedError('authentication_required' if code in (401,403) else 'rate_limited' if code==429 else 'http_error',code) from None
  with response:
   if response.geturl()!=config['url']:raise FeedError('unexpected_response_origin')
   if response.status!=200:raise FeedError('unexpected_http_status',response.status)
   media=response.headers.get('Content-Type','').split(';')[0].strip().lower()
   if media!='application/json' and not media.endswith('+json'):raise FeedError('json_content_type_required')
   if response.headers.get('Content-Encoding','identity').lower()!='identity':raise FeedError('unexpected_content_encoding')
   length=response.headers.get('Content-Length');declared=None
   if length is not None:
    if not re.fullmatch(r'\d+',length):raise FeedError('invalid_content_length')
    declared=int(length)
    if declared>config['max_bytes']:raise FeedError('response_size_limit')
   chunks=[];size=0
   while True:
    if clock()-started>config['max_seconds']:raise FeedError('download_time_limit')
    chunk=response.read(min(65536,config['max_bytes']-size+1))
    if not chunk:break
    chunks.append(chunk);size+=len(chunk)
    if size>config['max_bytes']:raise FeedError('response_size_limit')
   if declared is not None and declared!=size:raise FeedError('incomplete_response')
   tag=response.headers.get('ETag')
   if tag and (len(tag)>512 or any(ord(c)<32 or ord(c)>126 for c in tag) or token and token in tag):tag=None
   return {'not_modified':False,'raw':b''.join(chunks),'etag':tag}
 except FeedError:raise
 except Exception:raise FeedError('transport_failure') from None

def publish(path,raw):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temporary=None
 try:
  with tempfile.NamedTemporaryFile(dir=path.parent,prefix='.scan-feed-',delete=False) as f:
   temporary=Path(f.name);f.write(raw);f.flush();os.fsync(f.fileno())
  os.replace(temporary,path)
 finally:
  if temporary and temporary.exists():temporary.unlink()

class Feed:
 def __init__(self,config_path,*,fetch=download,environ=None):
  self.config_path=Path(config_path);self.config,self.config_raw=config_file(config_path);self.fetch=fetch;self.environ=environ;self.runtime=Path(self.config['runtime']);self.series=engine.sha(engine.canonical({'url':self.config['url'],'destination':self.config['destination'],'audit_runtime':self.config['audit_runtime']}))
 def head(self,e):
  for row in e.db.execute('SELECT event_json FROM events ORDER BY seq DESC'):
   event=json.loads(row[0]);p=event['payload']
   if event['action']=='feed.accepted' and p.get('series')==self.series:
    run=e.db.execute('SELECT snapshot_hash,policy_json FROM runs WHERE id=?',(p['run_id'],)).fetchone()
    if not run or run[0]!=p['snapshot']:raise FeedError('feed_cursor_integrity_failure')
    if p['artifacts'].get('configuration')!=p['config_sha256'] or p['artifacts'].get('policy')!=p['policy_sha256']:raise FeedError('feed_cursor_artifact_mismatch')
    for ref in p['artifacts'].values():
     obj=e.db.execute('SELECT object_path FROM snapshots WHERE hash=?',(ref,)).fetchone()
     if not obj:raise FeedError('feed_artifact_missing')
    policy_object=e.db.execute('SELECT object_path FROM snapshots WHERE hash=?',(p['policy_sha256'],)).fetchone()
    if engine.canonical(strict_json((e.root/policy_object[0]).read_bytes()))!=run['policy_json']:raise FeedError('feed_policy_run_mismatch')
    return p
  return None
 def step(self):
  c=self.config
  if any(Path(__file__).with_name(name).read_bytes()!=raw for name,raw in LOADED.items()):raise FeedError('implementation_changed_restart_required')
  if self.config_path.read_bytes()!=self.config_raw:raise FeedError('configuration_changed_restart_required')
  if not c['enabled']:return {'status':'disabled','reason':'feed_not_enabled'}
  with Path(c['policy']).open('rb') as f:policy_raw=f.read(100001)
  if len(policy_raw)>100000:raise FeedError('policy_size_limit')
  policy=engine.validate_policy(strict_json(policy_raw));policy_hash=engine.sha(policy_raw)
  with engine.Engine(c['audit_runtime']) as e:
   e.verify();head=self.head(e);tag=head.get('etag') if head and head['policy_sha256']==policy_hash and head['config_sha256']==engine.sha(self.config_raw) and engine.file_hash(c['destination'])==head['snapshot'] else None
  response=self.fetch(c,tag,environ=self.environ)
  if response['not_modified']:
   if not head or not tag:raise FeedError('unbacked_not_modified_response')
   with engine.Engine(c['audit_runtime']) as e:
    e.verify();current=self.head(e)
    if current!=head or engine.file_hash(c['destination'])!=head['snapshot']:raise FeedError('cached_source_changed_during_download')
   return {'status':'healthy','unchanged':True,'run_id':head['run_id'],'snapshot':head['snapshot']}
  raw=response['raw']
  if len(raw)>min(c['max_bytes'],policy['max_source_bytes']):raise FeedError('source_size_limit')
  try:
   source=strict_json(raw);engine.validate_scan(source)
   if isinstance(source.get('total'),bool) or not isinstance(source.get('total'),int):raise ValueError('invalid_total')
  except (ValueError,UnicodeError,TypeError):raise FeedError('invalid_scan_contract') from None
  with engine.Engine(c['audit_runtime']) as e:
   original=e.store_object(raw);result=e.ingest(original,policy)
   if result['snapshot']!=engine.sha(raw):raise FeedError('accepted_source_digest_mismatch')
   # The published inbox is materialized only after an accepted, archived run.
   publish(c['destination'],raw)
   artifacts={'configuration':self.config_raw,'policy':policy_raw,'connector_implementation':engine.code_bundle(LOADED)}
   objects={role:(engine.sha(content),e.store_object(content)) for role,content in artifacts.items()}
   payload={'series':self.series,'run_id':result['run_id'],'snapshot':result['snapshot'],'config_sha256':engine.sha(self.config_raw),'policy_sha256':policy_hash,'etag':response.get('etag'),'artifacts':{role:value[0] for role,value in objects.items()}}
   e.db.execute('BEGIN IMMEDIATE')
   try:
    previous=self.head(e)
    if not previous or engine.canonical(previous)!=engine.canonical(payload):
     for hash_,path in objects.values():e.db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?)',(hash_,str(path.relative_to(e.root))))
     e.append('feed.accepted',payload)
    e.db.execute('COMMIT')
   except Exception:e.db.execute('ROLLBACK');raise
  return {'status':'healthy','unchanged':bool(result['reused']),'run_id':result['run_id'],'snapshot':result['snapshot']}
 def poll(self):
  health={'pid':os.getpid(),'checked_at':engine.now(),'mode':'authorized_scan_https_feed'}
  try:health.update(self.step())
  except FeedError as error:health.update(status='degraded',reason=error.reason,http_status=error.http_status)
  except Exception as error:health.update(status='degraded',reason='local_validation_or_storage_failure',error_type=type(error).__name__)
  if health['status']=='degraded':
   # Preserve failure transitions without error bodies, credential hashes or headers.
   payload={'series':self.series,'reason':health['reason'],'http_status':health.get('http_status'),'config_sha256':engine.sha(self.config_raw),'policy_file_sha256':engine.file_hash(self.config['policy'])};fingerprint=engine.sha(engine.canonical(payload));payload['failure_fingerprint']=fingerprint
   try:
    with engine.Engine(self.config['audit_runtime']) as e:
     e.verify();cursor=self.head(e)
     if cursor:health['last_accepted']={'run_id':cursor['run_id'],'snapshot':cursor['snapshot']}
     e.db.execute('BEGIN IMMEDIATE')
     try:
      previous=None
      for row in e.db.execute('SELECT event_json FROM events ORDER BY seq DESC'):
       event=json.loads(row[0])
       if event['action'] in ['feed.failed','feed.accepted'] and event['payload'].get('series')==self.series:previous=event;break
      if not previous or previous['action']!='feed.failed' or previous['payload'].get('failure_fingerprint')!=fingerprint:e.append('feed.failed',payload)
      e.db.execute('COMMIT')
     except Exception:e.db.execute('ROLLBACK');raise
   except Exception:health['failure_history_unverified']=True
  atomic(self.runtime/'health.json',health);return health

def watch(feed,iterations=None):
 with exclusive(feed.runtime/'scan-feed.lock'):
  count=0
  while True:
   result=feed.poll();count+=1
   if iterations is not None and count>=iterations:return result
   time.sleep(feed.config['interval'])

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',type=Path,required=True);p.add_argument('--once',action='store_true');a=p.parse_args();print(engine.canonical(watch(Feed(a.config),1 if a.once else None)))
