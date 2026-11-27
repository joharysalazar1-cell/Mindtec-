"""Send a verified prepared package to its bound private Site and retain readback."""
import argparse,hashlib,json,os,re,ssl,sys,time,urllib.error,urllib.parse,urllib.request,math,email.utils
from pathlib import Path
import engine,supervisor,windows_job
from supervisor import exclusive,atomic

LOADED={'engine.py':engine.IMPLEMENTATION_BYTES,'supervisor.py':supervisor.IMPLEMENTATION_BYTES,'windows_job.py':Path(windows_job.__file__).read_bytes(),Path(__file__).name:Path(__file__).read_bytes()}
HEX=re.compile(r'[a-f0-9]{64}')
class SyncError(Exception):
 def __init__(self,reason,status=None,retry_after=None):super().__init__(reason);self.reason=reason;self.status=status;self.retry_after=retry_after
def retry_after(value,now=None):
 if not isinstance(value,str) or len(value)>128:return None
 value=value.strip()
 if re.fullmatch(r'[0-9]{1,9}',value):return int(value)
 try:
  instant=email.utils.parsedate_to_datetime(value)
  if instant.tzinfo is None:return None
  return max(0,math.ceil(instant.timestamp()-(time.time() if now is None else now)))
 except (TypeError,ValueError,OverflowError):return None
def require(value,reason):
 if not value:raise SyncError(reason)
def parsed(raw):
 def pairs(items):
  result={}
  for key,value in items:
   require(key not in result,'duplicate_json_key');result[key]=value
  return result
 def nonfinite(value):raise SyncError('nonfinite_json')
 try:return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=pairs,parse_constant=nonfinite)
 except SyncError:raise
 except Exception:raise SyncError('invalid_json') from None
def origin(value):
 try:
  u=urllib.parse.urlsplit(value);ok=isinstance(value,str) and value.startswith('https://') and not any(c.isspace() or ord(c)<32 for c in value) and u.hostname and ':' not in u.hostname and u.port in (None,443) and not u.username and not u.password and u.path in ('','/') and not u.query and not u.fragment
 except (ValueError,TypeError):ok=False
 require(ok,'https_site_origin_required');return 'https://'+u.hostname.lower()
def config_file(path):
 with Path(path).open('rb') as f:raw=f.read(100001)
 require(len(raw)<=100000,'config_size_limit');c=parsed(raw)
 require(isinstance(c,dict) and set(c)=={'schema','enabled','origin','project_id','outbox_runtime','runtime','token_env','timeout','max_seconds'},'config_contract')
 require(c['schema']=='mindtec-sync-client/1' and isinstance(c['enabled'],bool),'config_contract');c['origin']=origin(c['origin'])
 require(isinstance(c['project_id'],str) and re.fullmatch(r'appgprj_[a-zA-Z0-9]+',c['project_id']),'site_project_required')
 require(isinstance(c['token_env'],str) and re.fullmatch(r'MINDTEC_[A-Z0-9_]{1,80}',c['token_env']),'dedicated_service_credential_required')
 for k in ['outbox_runtime','runtime']:require(isinstance(c[k],str) and Path(c[k]).is_absolute(),'absolute_custody_paths_required')
 a,b=Path(c['outbox_runtime']).resolve(),Path(c['runtime']).resolve();require(not a.is_relative_to(b) and not b.is_relative_to(a),'separate_delivery_custody_required')
 for k,lo,hi in [('timeout',1,30),('max_seconds',1,120)]:require(isinstance(c[k],int) and not isinstance(c[k],bool) and lo<=c[k]<=hi,'invalid_transport_limits')
 return c,raw
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,request,fp,code,msg,headers,newurl):
  if fp is not None:fp.close()
  raise SyncError('redirect_rejected',code)
class Transport:
 def __init__(self,config,token,*,opener=None,clock=time.monotonic):
  require(isinstance(token,str) and 0<len(token)<=10000 and all(33<=ord(c)<=126 for c in token),'service_credential_missing_or_invalid')
  self.c=config;self.token=token;self.clock=clock;self.opener=opener or urllib.request.build_opener(NoRedirect(),urllib.request.HTTPSHandler(context=ssl.create_default_context()))
 def exchange(self,method,path,raw=None,binary=False,limit=30000000):
  require(isinstance(limit,int) and 0<limit<=100000000,'invalid_response_limit')
  require(method in ('GET','POST') and path.startswith('/api/service-sync/') and not any(c in path for c in ['\r','\n','#','\\']) and urllib.parse.urlsplit(path).netloc=='','invalid_service_path')
  url=self.c['origin']+path;headers={'Accept':'application/json','Accept-Encoding':'identity','Origin':self.c['origin'],'OAI-Sites-Authorization':'Bearer '+self.token,'User-Agent':'MindTEC-audit-sync/1'}
  if method=='POST':headers['Content-Type']='application/octet-stream' if binary else 'application/json'
  request=urllib.request.Request(url,data=raw,headers=headers,method=method);start=self.clock()
  try:
   with self.opener.open(request,timeout=self.c['timeout']) as r:
    require(r.geturl()==url,'unexpected_response_origin');require(r.status in (200,201),'unexpected_http_status')
    require(r.headers.get('Content-Encoding','identity').lower()=='identity','unexpected_response_encoding')
    media=r.headers.get('Content-Type','').split(';')[0].strip().lower();require(media=='application/json' or binary and media=='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','unexpected_response_type')
    length=r.headers.get('Content-Length');declared=None
    if length is not None:require(re.fullmatch(r'[0-9]{1,12}',length) is not None,'invalid_content_length');declared=int(length);require(declared<=limit,'response_size_limit')
    chunks=[];size=0
    while True:
     require(self.clock()-start<=self.c['max_seconds'],'response_time_limit');chunk=r.read(min(65536,limit-size+1))
     if not chunk:break
     chunks.append(chunk);size+=len(chunk);require(size<=limit,'response_size_limit')
    require(declared is None or declared==size,'incomplete_response');return b''.join(chunks),r.headers.get('X-Content-SHA256')
  except urllib.error.HTTPError as error:
   code=error.code;delay=retry_after(error.headers.get('Retry-After')) if error.headers else None;error.close();raise SyncError('authentication_required' if code in (401,403) else 'rate_limited' if code==429 else 'http_error',code,delay) from None
  except SyncError:raise
  except Exception:raise SyncError('transport_failure') from None
 def post(self,path,raw,binary=False):
  data,_=self.exchange('POST','/api/service-sync'+path,raw,binary);body=parsed(data);require(isinstance(body,dict) and isinstance(body.get('id'),str) and HEX.fullmatch(body['id']),'invalid_remote_acceptance');return body,data
 def get(self,path,expected=None,binary=False,limit=30000000):
  raw,header=self.exchange('GET','/api/service-sync'+path,binary=binary,limit=limit);require(isinstance(header,str) and HEX.fullmatch(header) and engine.sha(raw)==header,'remote_readback_digest_mismatch')
  if expected:require(header==expected,'remote_readback_differs_from_acceptance')
  return raw

class Client:
 def __init__(self,config_path,*,transport=None,token=None,progress=None):
  self.path=Path(config_path);self.c,self.config_raw=config_file(self.path);self.runtime=Path(self.c['runtime']);self.transport=transport;self.token=token;self.progress=progress or (lambda stage:None);self.stage='initial';self.package=None
 def mark(self,stage):self.stage=stage;self.progress(stage)
 def capture(self):
  root=Path(self.c['outbox_runtime']).resolve();require((root/'audit.sqlite').is_file(),'outbox_not_available')
  with engine.Engine(root) as e:
   e.verify();run=None;manifest=None;raw=None
   for row in e.db.execute('SELECT * FROM runs ORDER BY at DESC'):
    if parsed(row['rules_json'].encode()).get('kind')!='sync_outbox':continue
    obj=e.db.execute('SELECT object_path FROM snapshots WHERE hash=?',(row['snapshot_hash'],)).fetchone();p=(root/obj[0]).resolve();require(p.is_relative_to(root),'outbox_artifact_outside_custody');candidate=p.read_bytes();m=parsed(candidate)
    if m.get('target')=={'origin':self.c['origin'],'project_id':self.c['project_id']}:run=dict(row);manifest=m;raw=candidate;break
   require(run is not None,'no_prepared_package_for_site');require(len(raw)<=150000,'manifest_size_limit');require(manifest.get('schema')=='mindtec-sync-package/1' and manifest.get('version')=='mindtec-sync-outbox/1.0.0' and manifest.get('state')=='prepared_not_sent','unsupported_prepared_package');require(engine.sha(raw)==run['snapshot_hash'],'outbox_manifest_digest_mismatch')
   catalog={r['hash']:(root/r['object_path']).resolve() for r in e.db.execute('SELECT * FROM snapshots')};refs=parsed(run['rules_json'].encode())['reference_sources'];require(refs=={k:a['sha256'] for k,a in manifest['artifacts'].items()},'outbox_reference_contract')
  self.package={'run':run,'manifest':manifest,'raw':raw,'root':root,'catalog':catalog};return self.package
 def artifact(self,role,limit):
  p=self.package;a=p['manifest']['artifacts'].get(role);require(a is not None,'required_artifact_missing');path=p['catalog'].get(a['sha256']);require(path and path.is_relative_to(p['root']) and path.suffix==a['extension'],'invalid_artifact_path')
  with path.open('rb') as f:raw=f.read(limit+1)
  require(len(raw)<=limit and len(raw)==a['bytes'] and engine.sha(raw)==a['sha256'],'artifact_size_or_digest_mismatch');return raw
 def expected_roles(self):return ['scan.source','scan.policy','invoice.source','invoice.policy','invoice.reference.current_workbook','web.lineage_dependencies']+(['invoice.reference.previous_cut','invoice.reference.previous_workbook'] if 'invoice.reference.previous_cut' in self.package['manifest']['artifacts'] else [])
 def check_receipt(self,result,mappings):
  p=self.package;require(result.get('schema')=='mindtec-sync-receipt/1' and result.get('state')=='remote_inputs_verified' and result.get('package_sha256')==p['run']['snapshot_hash'] and result.get('local_package_run_id_declared')==p['run']['id'],'receipt_package_mismatch')
  expected={**mappings,'workbooks':sorted(mappings['workbooks'])};require(result.get('mappings')==expected,'receipt_mapping_mismatch')
  verified={k:p['manifest']['artifacts'][k]['sha256'] for k in self.expected_roles()};require(result.get('verified_artifacts')==verified,'receipt_artifact_scope_mismatch')
  require(result.get('unverified_local_artifacts')==sorted(set(p['manifest']['artifacts'])-set(verified)) and result.get('local_ledger_verified') is False and result.get('parent_bytes_verified_on_server') is False and result.get('numeric_parity_claimed') is False,'receipt_overstates_verified_scope')
  for family,role in [('scan','scan.source'),('invoice','invoice.source'),('lineage','web.lineage_dependencies')]:
   run=result.get('remote_runs',{}).get(family,{});require(run.get('id')==mappings[family] and run.get('source_sha256')==p['manifest']['artifacts'][role]['sha256'] and all(isinstance(run.get(k),str) and HEX.fullmatch(run[k]) for k in ['findings_sha256','implementation_sha256']),'receipt_remote_source_mismatch')
 def previous(self):
  if not (self.runtime/'audit.sqlite').is_file():return None
  with engine.Engine(self.runtime) as e:
   e.verify()
   for r in e.db.execute('SELECT * FROM runs ORDER BY at DESC'):
    rules=parsed(r['rules_json'].encode())
    if rules.get('kind')=='sync_delivery' and rules.get('local_package_run_id')==self.package['run']['id'] and rules.get('origin')==self.c['origin']:
     path=e.db.execute('SELECT object_path FROM snapshots WHERE hash=?',(r['snapshot_hash'],)).fetchone();return dict(r),parsed((e.root/path[0]).read_bytes())
  return None
 def step(self):
  require(all(Path(__file__).with_name(n).read_bytes()==b for n,b in LOADED.items()),'implementation_changed_restart_required');require(self.path.read_bytes()==self.config_raw,'configuration_changed_restart_required')
  if not self.c['enabled']:return {'status':'disabled','state':'delivery_not_enabled'}
  self.mark('verify_local_package');self.capture();previous=self.previous()
  if self.transport is None:self.transport=Transport(self.c,self.token if self.token is not None else os.environ.get(self.c['token_env']))
  if previous:
   self.mark('recheck_previous_remote_receipt');record,ack=previous;require(ack.get('schema')=='mindtec-sync-acknowledgment/1' and ack.get('origin')==self.c['origin'] and ack.get('project_id')==self.c['project_id'] and all(isinstance(ack.get(k),str) and HEX.fullmatch(ack[k]) for k in ['remote_receipt_id','remote_receipt_sha256']),'local_acknowledgment_contract');result_raw=self.transport.get('/sync/receipts/'+ack['remote_receipt_id']+'/result',ack['remote_receipt_sha256']);result=parsed(result_raw);self.check_receipt(result,ack['mappings']);return {'status':'healthy','state':'delivered_verified','run_id':record['id'],'local_package_run_id':self.package['run']['id'],'remote_receipt_id':ack['remote_receipt_id'],'reused':True}
  # Read and hash every transferable artifact before creating any remote run.
  raw={k:self.artifact(k,100000 if k.endswith('.policy') else 25000000 if 'workbook' in k else 10000000) for k in self.expected_roles()};mappings={'workbooks':[]}
  self.mark('send_scan_policy');policy,_=self.transport.post('/audit/policies',raw['scan.policy']);self.mark('evaluate_scan');run,_=self.transport.post('/audit/runs?policy='+policy['id'],raw['scan.source']);mappings['scan']=run['id']
  self.mark('send_invoice_policy');policy,_=self.transport.post('/invoices/policies',raw['invoice.policy']);prior=None
  if 'invoice.reference.previous_cut' in raw:
   self.mark('evaluate_previous_invoice_cut');run,_=self.transport.post('/invoices/runs?policy='+policy['id'],raw['invoice.reference.previous_cut']);prior=run['id']
  self.mark('evaluate_current_invoice_cut');run,_=self.transport.post('/invoices/runs?policy='+policy['id']+('&reference='+prior if prior else ''),raw['invoice.source']);mappings['invoice']=run['id']
  for side,role in [('current','invoice.reference.current_workbook'),*([('reference','invoice.reference.previous_workbook')] if prior else [])]:
   self.mark('verify_'+side+'_workbook');proof,_=self.transport.post('/invoices/runs/'+run['id']+'/workbook-verifications?side='+side,raw[role],True);mappings['workbooks'].append(proof['id'])
  self.mark('evaluate_lineage');lineage,_=self.transport.post('/lineage/runs?invoice='+mappings['invoice']+'&scan='+mappings['scan'],raw['web.lineage_dependencies']);mappings['lineage']=lineage['id'];mappings['workbooks'].sort()
  request={'schema':'mindtec-sync-request/1','local_package_run_id':self.package['run']['id'],'manifest_text':self.package['raw'].decode('utf-8'),'manifest_sha256':self.package['run']['snapshot_hash'],'mappings':mappings,'policy_sources':{k:raw[k+'.policy'].decode('utf-8') for k in ['scan','invoice']}};request_raw=engine.canonical(request).encode()
  require(len(request_raw)<=500000,'receipt_request_size_limit');self.mark('create_remote_receipt');receipt,response_raw=self.transport.post('/sync/receipts',request_raw);receipt_id=receipt['id'];metadata=receipt.get('receipt',{});require(metadata.get('id')==receipt_id and isinstance(metadata.get('result_sha256'),str) and HEX.fullmatch(metadata['result_sha256']),'invalid_remote_receipt')
  self.mark('readback_remote_receipt');base='/sync/receipts/'+receipt_id
  result_raw=self.transport.get(base+'/result',metadata.get('result_sha256'));result=parsed(result_raw);require(result.get('id')==receipt_id,'receipt_identity_mismatch');self.check_receipt(result,mappings)
  manifest_raw=self.transport.get(base+'/manifest',self.package['run']['snapshot_hash']);require(manifest_raw==self.package['raw'],'remote_manifest_bytes_mismatch')
  stored_request=self.transport.get(base+'/request',engine.sha(request_raw));require(stored_request==request_raw,'remote_request_bytes_mismatch')
  require(isinstance(result.get('implementation_sha256'),str) and HEX.fullmatch(result['implementation_sha256']),'receipt_code_digest_missing');code_raw=self.transport.get(base+'/code',result['implementation_sha256']);code=parsed(code_raw);require(code.get('schema')=='mindtec-web-code-bundle/1' and 'sync-receipts.mjs' in code.get('files',{}),'receipt_code_bundle_invalid')
  # Acknowledgment is durable only after independent GET readback, never from
  # the POST's success status or summary alone.
  ack={'schema':'mindtec-sync-acknowledgment/1','state':'delivered_verified','origin':self.c['origin'],'project_id':self.c['project_id'],'local_package_run_id':self.package['run']['id'],'local_manifest_sha256':self.package['run']['snapshot_hash'],'remote_receipt_id':receipt_id,'remote_receipt_sha256':engine.sha(result_raw),'mappings':mappings,'scope':'Transferred inputs verified; local ledger and full parents not verified remotely.'}
  refs={'local_manifest':(self.package['raw'],'.json'),'local_package_run_record':(engine.canonical(self.package['run']).encode(),'.json'),'request':(request_raw,'.json'),'post_response':(response_raw,'.json'),'remote_result':(result_raw,'.json'),'remote_code':(code_raw,'.json'),'configuration':(self.config_raw,'.json'),'implementation_bundle':(engine.code_bundle(LOADED),'.json')};policy={'schema':'mindtec-sync-delivery-policy/1','version':'1.0.0-readback-required'};rules={'kind':'sync_delivery','engine_version':'sync-client/1.0.0','local_package_run_id':self.package['run']['id'],'origin':self.c['origin'],'reference_sources':{k:engine.sha(v[0]) for k,v in refs.items()}}
  self.mark('retain_local_acknowledgment')
  with engine.Engine(self.runtime) as e:accepted=e.record_result(engine.canonical(ack).encode(),policy,rules,[],{'state':'delivered_verified','verified_input_roles':len(result['verified_artifacts'])},refs)
  return {'status':'healthy','state':'delivered_verified','run_id':accepted['run_id'],'local_package_run_id':ack['local_package_run_id'],'remote_receipt_id':receipt_id,'reused':accepted['reused']}
 def poll(self):
  health={'pid':os.getpid(),'checked_at':engine.now(),'mode':'site_sync_client_one_shot'}
  try:health.update(self.step())
  except Exception as error:
   reason=error.reason if isinstance(error,SyncError) else 'local_validation_or_storage_failure';status=getattr(error,'status',None);health.update(status='degraded',state='delivery_not_confirmed',stage=self.stage,reason=reason,http_status=status,retry_after_seconds=getattr(error,'retry_after',None))
   payload={'stage':self.stage,'reason':reason,'http_status':status,'local_package_run_id':self.package['run']['id'] if self.package else None,'config_sha256':engine.sha(self.config_raw)}
   try:
    with engine.Engine(self.runtime) as e:
     e.verify();last=e.db.execute('SELECT event_json FROM events ORDER BY seq DESC LIMIT 1').fetchone();previous=parsed(last[0].encode()) if last else None
     if not previous or previous['action']!='sync.delivery.failed' or previous['payload']!=payload:
      e.db.execute('BEGIN IMMEDIATE')
      try:e.append('sync.delivery.failed',payload);e.db.execute('COMMIT')
      except Exception:e.db.execute('ROLLBACK');raise
   except Exception:health['failure_history_unverified']=True
  atomic(self.runtime/'health.json',health);return health
 def run(self):
  with exclusive(self.runtime/'sync-client.lock'):return self.poll()

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--config',required=True,type=Path);p.add_argument('--credential-stdin',action='store_true');a=p.parse_args();token=None
 if a.credential_stdin:
  require(not sys.stdin.isatty(),'credential_stdin_requires_hidden_pipe');data=parsed(sys.stdin.buffer.readline(20001));require(isinstance(data,dict) and set(data)=={'token'},'credential_input_contract');token=data['token']
 client=Client(a.config,token=token,progress=lambda stage:print(engine.canonical({'stage':stage}),flush=True));outcome=client.run();print(engine.canonical(outcome));raise SystemExit(0 if outcome['status'] in ['healthy','disabled'] else 1)
