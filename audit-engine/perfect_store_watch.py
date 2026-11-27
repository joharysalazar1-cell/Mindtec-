"""Continuously verify an admitted PS cut locally; preserve last valid evidence."""
import argparse,base64,collections,os,time,uuid
from pathlib import Path
import engine,supervisor,collection_watch,perfect_store_admission as admission
import perfect_store,perfect_store_findings,perfect_store_check,perfect_store_report

NAMES=['engine.py','supervisor.py','windows_job.py','invoice_adapter.py','collection_adapter.py','collection_audit.py','collection_watch.py','flat_answers.py','category_eligibility.py','perfect_store.py','perfect_store_findings.py','perfect_store_check.py','perfect_store_report.py','perfect_store_admission.py',Path(__file__).name]
LOADED={name:Path(__file__).with_name(name).read_bytes() for name in NAMES}

class Observer:
 def __init__(self,admission_file,runtime,report_dir):
  self.admission=Path(admission_file).resolve();self.runtime=Path(runtime).resolve();self.report_dir=Path(report_dir).resolve()
  if self.admission.is_relative_to(self.runtime) or self.admission.is_relative_to(self.report_dir) or self.runtime.is_relative_to(self.report_dir) or self.report_dir.is_relative_to(self.runtime):raise ValueError('Admission, evidence runtime and reports must remain separate')
  self.series=engine.sha(engine.canonical({'admission':str(self.admission),'runtime':str(self.runtime),'report_dir':str(self.report_dir)}));self.bundle=engine.code_bundle(LOADED);self.last_accepted=None
 def prior(self):
  with engine.Engine(self.runtime) as e:
   e.verify()
   for row in e.db.execute('SELECT event_json FROM events ORDER BY seq DESC'):
    event=engine.load_json_bytes(row[0].encode())
    if event['action']!='perfect_store.observer.accepted':continue
    p=event['payload']
    if p['series']!=self.series:raise ValueError('Runtime belongs to another admitted Perfect Store series')
    run=e.db.execute('SELECT * FROM runs WHERE id=?',(p['run_id'],)).fetchone()
    if not run:raise ValueError('Accepted Perfect Store execution missing')
    rules=engine.load_json_bytes(run['rules_json'].encode());refs=rules['reference_sources']
    if rules.get('kind')!='operational_perfect_store' or rules.get('series')!=self.series or rules.get('context_sha256')!=p['context_sha256'] or refs['admission_manifest']!=p['admission_sha256']:raise ValueError('Accepted Perfect Store source binding differs')
    path=Path(p['report_path']).resolve()
    if not path.is_relative_to(self.report_dir):raise ValueError('Accepted report is outside selected report directory')
    envelope=engine.load_json_bytes(collection_watch.object_bytes(e,p['report_object_sha256']))
    if envelope.get('schema')!='mindtec-retained-html/1' or envelope.get('encoding')!='base64':raise ValueError('Retained report envelope differs')
    retained=base64.b64decode(envelope['content'],validate=True)
    if engine.sha(retained)!=p['report_sha256'] or envelope['sha256']!=p['report_sha256']:raise ValueError('Retained report fingerprint differs')
    if not path.exists():
     path.parent.mkdir(parents=True,exist_ok=True)
     with path.open('xb') as f:f.write(retained)
    if engine.sha(path.read_bytes())!=p['report_sha256']:raise ValueError('Accepted report bytes differ from custody')
    return p
  return None
 def poll(self):
  health={'pid':os.getpid(),'checked_at':engine.now(),'mode':'admitted_operational_perfect_store','network_delivery':False,'last_accepted':self.last_accepted,'custody_verified':False};candidate={}
  try:
   if any(Path(__file__).with_name(n).read_bytes()!=raw for n,raw in LOADED.items()):raise ValueError('Implementation changed; restart Perfect Store observer')
   prior=self.prior()
   if self.last_accepted and not prior:raise ValueError('Previously accepted Perfect Store execution disappeared')
   self.last_accepted=prior;health.update(last_accepted=prior,custody_verified=prior is not None)
   raw=collection_watch.bounded(self.admission,100000);candidate['admission_manifest']=(raw,'.json');a=admission.contract(raw,self.runtime,self.report_dir);raw_sources={}
   for role,limit in admission.SOURCE_LIMITS.items():
    data=collection_watch.bounded(a['sources'][role]['path'],limit);candidate[role]=(data,'.xlsx' if role.endswith('workbook') else '.json');raw_sources[role]=data
    if engine.sha(data)!=a['sources'][role]['sha256']:raise ValueError('Admitted source fingerprint differs: '+role)
   context=engine.sha(engine.canonical({'admission':engine.sha(raw),'implementation':engine.sha(self.bundle)}))
   if not prior or context!=prior['context_sha256']:
    # Processing is visible; no incomplete result is declared healthy.
    supervisor.atomic(self.runtime/'health.json',{**health,'status':'processing','checked_at':engine.now()})
    prepared=admission.prepare(a,raw_sources);result=perfect_store.evaluate(prepared['flat'],prepared['catalog'],prepared['policy'],prepared['configuration'])
    result.update(catalogue_source_sha256=engine.sha(raw_sources['normalized_result_workbook']),configuration_provenance=prepared['configuration'].get('provenance',{}))
    checks={**perfect_store_check.verify_model(result),**perfect_store_check.verify_cells(result,prepared['detailed_book'])};findings=perfect_store_findings.evaluate(result)
    summary={**prepared['coverage'],'included_visits':sum(a['expected_eligible_counts'].values()),'store_rows':len(result['details']),'monthly_results':len(result['monthly']),'complete_monthly_results':sum(r['score'] is not None for r in result['monthly']),'complete_store_scores':sum(r['score'] is not None for r in result['details']),'component_states':dict(collections.Counter(c['state'] for r in result['details'] for c in r['components'])),'category_review_findings':len(findings),'independent_checks':checks,'not_official_kernel':True,'network_delivery':False}
    refs={**candidate,'implementation':(self.bundle,'.json')};rules={'kind':'operational_perfect_store','version':perfect_store.VERSION,'observer_version':'1','series':self.series,'context_sha256':context,'admission_version':a['version'],'admission_label':a['label'],'reference_sources':{k:engine.sha(v[0]) for k,v in refs.items()}}
    with engine.Engine(self.runtime) as e:accepted=e.record_result(engine.canonical(result).encode(),prepared['policy'],rules,findings,summary,refs)
    self.report_dir.mkdir(parents=True,exist_ok=True);temp=self.report_dir/('building-'+uuid.uuid4().hex+'.html')
    try:
     perfect_store_report.export(self.runtime,temp,accepted['run_id']);report_raw=temp.read_bytes();report_sha=engine.sha(report_raw);report_path=self.report_dir/(report_sha+'.html')
     if report_path.exists():
      if report_path.read_bytes()!=report_raw:raise ValueError('Report fingerprint path collision')
      temp.unlink()
     else:os.replace(temp,report_path)
    finally:
     if temp.exists():temp.unlink()
    report_object=engine.canonical({'schema':'mindtec-retained-html/1','encoding':'base64','sha256':report_sha,'content':base64.b64encode(report_raw).decode('ascii')}).encode()
    payload={'series':self.series,'run_id':accepted['run_id'],'context_sha256':context,'admission_sha256':engine.sha(raw),'report_path':str(report_path),'report_sha256':report_sha,'report_object_sha256':engine.sha(report_object),'coverage':prepared['coverage'],'finding_count':len(findings),'verification':checks}
    with engine.Engine(self.runtime) as e:
     e.verify();e.db.execute('BEGIN IMMEDIATE')
     try:
      obj=e.store_object(report_object,'.json');e.db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?)',(engine.sha(report_object),str(obj.relative_to(e.root))));e.append('perfect_store.observer.accepted',payload);e.db.execute('COMMIT')
     except Exception:e.db.execute('ROLLBACK');raise
    prior=self.prior()
   self.last_accepted=prior;health.update(status='healthy',run_id=prior['run_id'],last_accepted=prior,custody_verified=True,report_path=prior['report_path'],finding_count=prior['finding_count'],coverage=prior['coverage'])
  except Exception as error:
   health.update(status='degraded',reason=str(error),error_type=type(error).__name__,last_accepted=self.last_accepted)
   try:
    with engine.Engine(self.runtime) as e:
     e.verify();payload={'series':self.series,'error_type':type(error).__name__,'reason':str(error),'last_accepted':self.last_accepted,'retained_inputs':{k:engine.sha(v[0]) for k,v in candidate.items()}}
     last=e.db.execute('SELECT event_json FROM events ORDER BY seq DESC LIMIT 1').fetchone()
     if not last or engine.load_json_bytes(last[0].encode()).get('payload')!=payload:
      e.db.execute('BEGIN IMMEDIATE')
      try:
       for data,ext in candidate.values():
        obj=e.store_object(data,ext);e.db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?)',(engine.sha(data),str(obj.relative_to(e.root))))
       e.append('perfect_store.observer.rejected',payload);e.db.execute('COMMIT')
      except Exception:e.db.execute('ROLLBACK');raise
   except Exception:health['failure_history_unverified']=True
  health['checked_at']=engine.now();supervisor.atomic(self.runtime/'health.json',health);return health

def watch(observer,interval=60,iterations=None):
 if isinstance(interval,bool) or not isinstance(interval,(int,float)) or not 30<=interval<=3600:raise ValueError('Perfect Store polling interval must be 30 to 3600 seconds')
 with supervisor.exclusive(observer.runtime/'perfect-store-observer.lock'):
  count=0
  while True:
   health=observer.poll();count+=1
   if iterations is not None and count>=iterations:return health
   time.sleep(interval)

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['admission','runtime','report-dir']:p.add_argument('--'+name,required=True,type=Path)
 p.add_argument('--interval',type=float,default=60);p.add_argument('--iterations',type=int);a=p.parse_args()
 print(engine.canonical(watch(Observer(a.admission,a.runtime,a.report_dir),a.interval,a.iterations)))
