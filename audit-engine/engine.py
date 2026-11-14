"""Local, read-only Scan anomaly detection with an append-only evidence ledger."""
from __future__ import annotations
import argparse, collections, datetime as dt, hashlib, json, math, os,base64
from pathlib import Path
import re, sqlite3, time, tempfile,contextlib

ENGINE_VERSION='1.1.0'
RULES={
 'duplicate_visit':('1','high','Clave de envío duplicada'),
 'conflicting_answer':('1','high','Respuestas incompatibles en una misma ruta'),
 'category_contradiction':('1','medium','Declara no vender una categoría y enumera marcas'),
 'cold_zero_faces':('1','info','Marca enumerada en el grupo de frío con cero caras'),
 'invalid_number':('1','high','Medida de caras inválida'),
 'invalid_gps':('1','medium','Coordenadas fuera del dominio permitido'),
 'missing_sticker':('1','medium','Identificador de tienda ausente'),
}
def canonical(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def sha(v):return hashlib.sha256(v if isinstance(v,bytes) else v.encode('utf-8')).hexdigest()
IMPLEMENTATION_BYTES=Path(__file__).read_bytes()
IMPLEMENTATION_SHA=sha(IMPLEMENTATION_BYTES)
def code_bundle(files):return canonical({'schema':'mindtec-code-bundle/2','files':{name:{'encoding':'base64','sha256':sha(raw),'content':base64.b64encode(raw).decode('ascii')} for name,raw in files.items()}}).encode('utf-8')
def now():return dt.datetime.now(dt.timezone.utc).isoformat()
def load_json_bytes(raw):
 def reject(v):raise ValueError('Non-finite JSON number')
 return json.loads(raw.decode('utf-8-sig'),parse_constant=reject)
def validate_policy(p):
 if p.get('schema')!='mindtec-audit-policy/1' or not isinstance(p.get('version'),str) or not p['version'].strip():raise ValueError('Invalid policy schema/version')
 if not isinstance(p.get('max_source_bytes'),int) or not 0<p['max_source_bytes']<=100_000_000:raise ValueError('Invalid source size limit')
 if not isinstance(p.get('exclusions'),list):raise ValueError('Invalid exclusions')
 ids=set()
 for x in p['exclusions']:
  if not isinstance(x,dict) or not str(x.get('id','')).strip() or not str(x.get('reason','')).strip() or not str(x.get('evidence','')).strip():raise ValueError('Every exclusion needs id, reason and evidence')
  if str(x['id']) in ids:raise ValueError('Duplicate exclusion')
  ids.add(str(x['id']))
 return p
def validate_scan(data):
 if not isinstance(data,dict) or not isinstance(data.get('envios'),list):raise ValueError('Expected Scan object with envios list')
 if not data['envios']:raise ValueError('Empty export cannot replace last valid snapshot')
 if data.get('total')!=len(data['envios']):raise ValueError('Export total differs from record count')
 for r in data['envios']:
  if not isinstance(r,dict) or isinstance(r.get('envioKobo'),bool) or not isinstance(r.get('envioKobo'),(str,int)) or not str(r['envioKobo']).strip():raise ValueError('Every visit needs envioKobo')
  if not isinstance(r.get('respuestas'),list):raise ValueError('Every visit needs respuestas')
  for a in r['respuestas']:
   if not isinstance(a,dict) or not isinstance(a.get('ruta'),str) or not a['ruta'] or 'valor' not in a:raise ValueError('Every answer needs ruta and valor')
 return data
def detect(data,policy):
 """No modification, person scoring, fraud labels, or inference of interview duration."""
 exclusions={str(x['id']):x for x in policy['exclusions']};findings=[]
 def emit(rule,record,index,paths,observed,explanation):
  version,severity,title=RULES[rule]
  evidence={'record_index':index,'record_id':str(record['envioKobo']),'paths':paths,'observed':observed}
  finding={'rule':rule,'rule_version':version,'severity':severity,'title':title,'evidence':evidence,'explanation':explanation,'disposition':'needs_human_review'}
  finding['fingerprint']=sha(canonical({'rule':rule,'version':version,'evidence':evidence}))
  findings.append(finding)
 seen={}
 for i,r in enumerate(data['envios']):
  rid=str(r['envioKobo'])
  if rid in seen:emit('duplicate_visit',r,i,['envioKobo'],{'first_index':seen[rid],'duplicate_index':i},'Comparar los originales; no deduplicar automáticamente.')
  else:seen[rid]=i
  if rid in exclusions:continue
  fields=collections.defaultdict(list)
  for a in r['respuestas']:fields[a['ruta']].append(a['valor'])
  for path,values in fields.items():
   if len({canonical(v) for v in values})>1:emit('conflicting_answer',r,i,[path],values,'La ruta tiene varios valores; no elegir silenciosamente el último.')
  # Ambiguous paths are not used to derive further claims.
  values={p:v[0] for p,v in fields.items() if len({canonical(a) for a in v})==1}
  for path,value in values.items():
   if '/vende_' in path and value=='no':
    sibling=path.rsplit('/',1)[0]+'/marcas_'+path.rsplit('/vende_',1)[1]
    if str(values.get(sibling) or '').strip():emit('category_contradiction',r,i,[path,sibling],{'gate':value,'brands':values[sibling]},'Puede deberse a saltos, edición o normalización. Requiere revisión del cuestionario.')
   if re.search(r'/(caras_frias|caras_frio_[^/]+|caras_bsa_[^/]+|caras_lac_[^/]+)$',path):
    try:n=float(str(value).replace(',','.'));valid=math.isfinite(n) and n>=0 and n.is_integer()
    except (ValueError,TypeError):n=None;valid=False
    if not valid:emit('invalid_number',r,i,[path],value,'Las caras se declaran como conteos enteros no negativos; conservar la respuesta y confirmar la unidad.')
    elif n==0 and ('caras_frias' in path or '/caras_frio_' in path):
     prefix=path.rsplit('/',1)[0]+'/'
     selected=[p for p in values if p.startswith(prefix) and re.search(r'/(marca_fria_actual|marca_frio_act_[^/]+)$',p) and str(values[p] or '').strip()]
     if selected:emit('cold_zero_faces',r,i,[path,*selected],{p:values[p] for p in [path,*selected]},'La marca enumerada puede proceder de una repetición automática. Enumeración y caras positivas son criterios distintos; cero puede ser válido. Confirmar la definición del indicador.')
  if not str(r.get('codigoTienda') or '').strip():emit('missing_sticker',r,i,['codigoTienda'],r.get('codigoTienda'),'La ausencia impide unir por tienda; no prueba ausencia de visita.')
  lat,lon=r.get('latitud'),r.get('longitud')
  if lat is not None or lon is not None:
   valid=all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in (lat,lon))
   if not valid or not (-90<=lat<=90 and -180<=lon<=180):emit('invalid_gps',r,i,['latitud','longitud'],{'latitude':lat,'longitude':lon},'Comprobar formato y fuente. No se atribuye falsificación ni se usa una geocerca no acordada.')
 return findings

class Engine:
 def __init__(self,runtime):
  self.root=Path(runtime).resolve();self.root.mkdir(parents=True,exist_ok=True)
  (self.root/'objects').mkdir(exist_ok=True)
  self.db=sqlite3.connect(self.root/'audit.sqlite',timeout=30,isolation_level=None)
  self.db.row_factory=sqlite3.Row
  self.db.executescript('''PRAGMA journal_mode=WAL;
  CREATE TABLE IF NOT EXISTS events(seq INTEGER PRIMARY KEY,event_json TEXT NOT NULL,hash TEXT NOT NULL UNIQUE);
  CREATE TABLE IF NOT EXISTS snapshots(hash TEXT PRIMARY KEY,object_path TEXT NOT NULL);
  CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,snapshot_hash TEXT NOT NULL,policy_json TEXT NOT NULL,rules_json TEXT NOT NULL,findings_json TEXT NOT NULL,at TEXT NOT NULL);
  CREATE TRIGGER IF NOT EXISTS events_no_update BEFORE UPDATE ON events BEGIN SELECT RAISE(ABORT,'append only');END;
  CREATE TRIGGER IF NOT EXISTS events_no_delete BEFORE DELETE ON events BEGIN SELECT RAISE(ABORT,'append only');END;
  CREATE TRIGGER IF NOT EXISTS snapshots_no_update BEFORE UPDATE ON snapshots BEGIN SELECT RAISE(ABORT,'append only');END;
  CREATE TRIGGER IF NOT EXISTS snapshots_no_delete BEFORE DELETE ON snapshots BEGIN SELECT RAISE(ABORT,'append only');END;
  CREATE TRIGGER IF NOT EXISTS runs_no_update BEFORE UPDATE ON runs BEGIN SELECT RAISE(ABORT,'append only');END;
  CREATE TRIGGER IF NOT EXISTS runs_no_delete BEFORE DELETE ON runs BEGIN SELECT RAISE(ABORT,'append only');END;''')
  try:self.verify()
  except Exception:self.db.close();raise
 def close(self):self.db.close()
 def __enter__(self):return self
 def __exit__(self,*args):self.close()
 def store_object(self,raw,extension='.json'):
  if extension not in ('.json','.xlsx'):raise ValueError('Unsupported evidence extension')
  hash_=sha(raw);dest=self.root/'objects'/f'{hash_}{extension}'
  if dest.exists():
   if sha(dest.read_bytes())!=hash_:raise ValueError('Existing evidence object corrupted')
   return dest
  with tempfile.NamedTemporaryFile(dir=dest.parent,suffix='.tmp',delete=False) as f:
   temp=Path(f.name);f.write(raw);f.flush();os.fsync(f.fileno())
  try:
   try:os.link(temp,dest)
   except FileExistsError:
    if sha(dest.read_bytes())!=hash_:raise ValueError('Concurrent evidence object corrupted')
  finally:temp.unlink(missing_ok=True)
  return dest
 def append(self,action,payload,actor='local-audit-service'):
  last=self.db.execute('SELECT hash FROM events ORDER BY seq DESC LIMIT 1').fetchone()
  event={'at':now(),'actor':actor,'action':action,'payload':payload,'previous':last['hash'] if last else 'GENESIS'}
  text=canonical(event);self.db.execute('INSERT INTO events(event_json,hash) VALUES(?,?)',(text,sha(text)))
 def verify(self):
  previous='GENESIS';completed={};snapshot_ids=set();invoice_heads=[];retained=[]
  for row in self.db.execute('SELECT * FROM events ORDER BY seq'):
   event=json.loads(row['event_json'])
   if event['previous']!=previous or sha(row['event_json'])!=row['hash']:raise ValueError('Evidence ledger integrity failure')
   if event['action']=='audit.completed':completed[event['payload']['run_id']]=event['payload']
   if event['action']=='invoice.observer.accepted':invoice_heads.append(event['payload'])
   if event['action']=='invoice.observer.rejected':retained.extend(event['payload'].get('retained_inputs',{}).values())
   if event['action']=='ingestion.failed' and 'object_path' in event['payload']:
    obj=self.root/event['payload']['object_path']
    if not obj.is_file() or sha(obj.read_bytes())!=event['payload']['rejected_source_hash']:raise ValueError('Rejected source integrity failure')
   previous=row['hash']
  for row in self.db.execute('SELECT * FROM snapshots'):
   snapshot_ids.add(row['hash'])
   path=self.root/row['object_path']
   if not path.is_file() or sha(path.read_bytes())!=row['hash']:raise ValueError('Snapshot integrity failure')
  runs={}
  for row in self.db.execute('SELECT * FROM runs'):
   runs[row['id']]=row
   policy=json.loads(row['policy_json']);rules=json.loads(row['rules_json']);event=completed.get(row['id'])
   expected=sha(canonical({'snapshot':row['snapshot_hash'],'policy':policy,'rules':rules}))
   if row['snapshot_hash'] not in snapshot_ids or expected!=row['id'] or not event or event['snapshot']!=row['snapshot_hash'] or event['policy_hash']!=sha(row['policy_json']) or event['rules_hash']!=sha(row['rules_json']) or event['findings_hash']!=sha(row['findings_json']):raise ValueError('Run evidence integrity failure')
   references=rules.get('reference_sources',{})
   if references!=event.get('reference_sources',{}) or any(v not in snapshot_ids for v in references.values()):raise ValueError('Run reference integrity failure')
  for obj in retained:
   if obj['sha256'] not in snapshot_ids or not (self.root/obj['object_path']).is_file() or sha((self.root/obj['object_path']).read_bytes())!=obj['sha256']:raise ValueError('Rejected invoice input integrity failure')
  for head in invoice_heads:
   run=runs.get(head.get('run_id'));refs=json.loads(run['rules_json']).get('reference_sources',{}) if run else {}
   if not run or head['snapshot']!=run['snapshot_hash'] or head.get('reference_snapshot')!=refs.get('previous_cut') or head.get('original_workbook')!=refs.get('current_workbook') or head.get('reference_workbook')!=refs.get('previous_workbook'):raise ValueError('Invoice observer cursor integrity failure')
   if head.get('observer_bundle') and head['observer_bundle'] not in snapshot_ids:raise ValueError('Observer implementation evidence is missing')
   source=self.db.execute('SELECT object_path FROM snapshots WHERE hash=?',(head['snapshot'],)).fetchone()
   cut=load_json_bytes((self.root/source[0]).read_bytes())
   if sha(canonical(cut['scope']))!=head['scope_hash']:raise ValueError('Invoice cursor scope differs from preserved input')
  return previous
 def ingest(self,source,policy):
  policy=validate_policy(policy);self.verify()
  if sha(Path(__file__).read_bytes())!=IMPLEMENTATION_SHA:raise RuntimeError('Engine implementation changed; restart observer before accepting another run')
  with Path(source).open('rb') as f:raw=f.read(policy['max_source_bytes']+1)
  if len(raw)>policy['max_source_bytes']:raise ValueError('Source exceeds configured maximum')
  data=validate_scan(load_json_bytes(raw));source_hash=sha(raw)
  bundle=code_bundle({'engine.py':IMPLEMENTATION_BYTES})
  references={'implementation_bundle':(bundle,'.json')}
  rules={'engine_version':ENGINE_VERSION,'rules':RULES,'implementation_sha256':IMPLEMENTATION_SHA,'reference_sources':{'implementation_bundle':sha(bundle)}}
  run_id=sha(canonical({'snapshot':source_hash,'policy':policy,'rules':rules}))
  existing=self.db.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()
  if existing:return {'run_id':run_id,'snapshot':source_hash,'reused':True,'findings':json.loads(existing['findings_json'])}
  findings=detect(data,policy)
  return self.record_result(raw,policy,rules,findings,{'excluded_count':sum(str(r['envioKobo']) in {str(x['id']) for x in policy['exclusions']} for r in data['envios'])},references)
 def record_result(self,raw,policy,rules,findings,summary=None,references=None):
  """Internal adapter boundary: persist computed results with their exact inputs."""
  self.verify()
  if sha(Path(__file__).read_bytes())!=IMPLEMENTATION_SHA:raise RuntimeError('Engine implementation changed; restart observer before accepting another run')
  source_hash=sha(raw);run_id=sha(canonical({'snapshot':source_hash,'policy':policy,'rules':rules}))
  references=references or {}
  if {k:sha(v[0]) for k,v in references.items()}!=rules.get('reference_sources',{}):raise ValueError('Declared reference hashes do not match supplied evidence')
  existing=self.db.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()
  if existing:return {'run_id':run_id,'snapshot':source_hash,'reused':True,'findings':json.loads(existing['findings_json'])}
  dest=self.store_object(raw);objects={source_hash:dest}
  for data,extension in references.values():objects[sha(data)]=self.store_object(data,extension)
  self.db.execute('BEGIN IMMEDIATE')
  try:
   # Recheck after the write lock: independent observers must not fork a run.
   existing=self.db.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone()
   if existing:self.db.execute('ROLLBACK');return {'run_id':run_id,'snapshot':source_hash,'reused':True,'findings':json.loads(existing['findings_json'])}
   for hash_,path in objects.items():self.db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?)',(hash_,str(path.relative_to(self.root))))
   self.db.execute('INSERT INTO runs VALUES(?,?,?,?,?,?)',(run_id,source_hash,canonical(policy),canonical(rules),canonical(findings),now()))
   self.append('audit.completed',{'run_id':run_id,'snapshot':source_hash,'policy_hash':sha(canonical(policy)),'rules_hash':sha(canonical(rules)),'findings_hash':sha(canonical(findings)),'finding_count':len(findings),'reference_sources':rules.get('reference_sources',{}),'summary':summary or {}})
   self.db.execute('COMMIT')
  except Exception:self.db.execute('ROLLBACK');raise
  return {'run_id':run_id,'snapshot':source_hash,'reused':False,'findings':findings}
 def review(self,run_id,fingerprint,status,actor,note,evidence):
  if status not in ['en_revision','dato_confirmado','correccion_solicitada','diferencia_explicada','sin_evidencia_suficiente']:raise ValueError('Invalid review status')
  if not all(isinstance(s,str) and s.strip() for s in (actor,note,evidence)):raise ValueError('Reviewer, explanation and evidence required')
  self.verify();run=self.db.execute('SELECT findings_json FROM runs WHERE id=?',(run_id,)).fetchone()
  if not run or fingerprint not in {f['fingerprint'] for f in json.loads(run[0])}:raise ValueError('Finding not part of this run')
  self.db.execute('BEGIN IMMEDIATE')
  try:self.append('finding.reviewed',{'run_id':run_id,'fingerprint':fingerprint,'status':status,'note':note,'evidence':evidence},actor);self.db.execute('COMMIT')
  except Exception:self.db.execute('ROLLBACK');raise

def file_hash(path):
 try:
  h=hashlib.sha256()
  with Path(path).open('rb') as f:
   for block in iter(lambda:f.read(65536),b''):h.update(block)
  return h.hexdigest()
 except OSError as e:return type(e).__name__

def _watch(source,policy_path,runtime,interval,stop_after,engine):
 if interval<1:raise ValueError('Minimum interval: one second')
 count=0;failed=None;last=engine.db.execute('SELECT id,snapshot_hash,at FROM runs ORDER BY at DESC LIMIT 1').fetchone()
 last_success={'at':last['at'],'run_id':last['id'],'snapshot':last['snapshot_hash']} if last else None
 while True:
  health={'pid':os.getpid(),'checked_at':now(),'mode':'local_file_observer','source':str(Path(source).resolve()),'status':'checking','last_success':last_success}
  try:
   policy=load_json_bytes(Path(policy_path).read_bytes());r=engine.ingest(source,policy)
   last_success={'at':now(),'run_id':r['run_id'],'snapshot':r['snapshot']}
   health.update(status='healthy',last_success=last_success,finding_count=len(r['findings']),review_required_count=sum(f['severity']!='info' for f in r['findings']),informational_count=sum(f['severity']=='info' for f in r['findings']),counts=dict(collections.Counter(f['rule'] for f in r['findings'])))
   failed=None
  except Exception as error:
   # Errors do not advance the accepted version or replace its evidence.
   health.update(status='degraded',error_type=type(error).__name__,last_success=last_success)
   failure=sha(canonical({'source_hash':file_hash(source),'policy_hash':file_hash(policy_path),'error_type':type(error).__name__}))
   if failure!=failed:
    try:engine.verify()
    except ValueError:health['integrity_failed']=True
    else:
     payload={'failure_fingerprint':failure,'error_type':type(error).__name__}
     try:
      with Path(source).open('rb') as f:rejected=f.read(60_000_001)
      if len(rejected)<=60_000_000:
       rejected_hash=sha(rejected);obj=engine.store_object(rejected)
       payload.update(rejected_source_hash=rejected_hash,object_path=str(obj.relative_to(engine.root)))
     except OSError:pass
     engine.db.execute('BEGIN IMMEDIATE')
     try:engine.append('ingestion.failed',payload);engine.db.execute('COMMIT')
     except Exception:engine.db.execute('ROLLBACK');raise
    failed=failure
  target=Path(runtime)/'health.json';temp=target.with_suffix('.tmp');temp.write_text(canonical(health),encoding='utf-8');os.replace(temp,target)
  count+=1
  if stop_after is not None and count>=stop_after:return health
  time.sleep(interval)

@contextlib.contextmanager
def observer_lock(runtime):
 root=Path(runtime);root.mkdir(parents=True,exist_ok=True);f=(root/'scan-observer.lock').open('a+b');locked=False
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
  except OSError as e:raise RuntimeError('Another Scan observer owns this runtime') from e
  yield
 finally:
  if locked:
   f.seek(0)
   if os.name=='nt':msvcrt.locking(f.fileno(),msvcrt.LK_UNLCK,1)
   else:fcntl.flock(f,fcntl.LOCK_UN)
  f.close()

def watch(source,policy_path,runtime,interval=10,stop_after=None):
 with observer_lock(runtime):
  with Engine(runtime) as engine:return _watch(source,policy_path,runtime,interval,stop_after,engine)

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=['run','watch','verify']);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--source',type=Path);p.add_argument('--policy',type=Path);p.add_argument('--interval',type=float,default=10);p.add_argument('--iterations',type=int)
 a=p.parse_args()
 if a.command=='verify':print(canonical({'verified':True,'head':Engine(a.runtime).verify()}));return
 if not a.source or not a.policy:p.error('--source and --policy are required')
 if a.command=='watch':print(canonical(watch(a.source,a.policy,a.runtime,a.interval,a.iterations)));return
 r=Engine(a.runtime).ingest(a.source,load_json_bytes(a.policy.read_bytes()));print(canonical({k:v for k,v in r.items() if k!='findings'}|{'finding_count':len(r['findings']),'rules':dict(collections.Counter(f['rule'] for f in r['findings']))}))
if __name__=='__main__':main()
