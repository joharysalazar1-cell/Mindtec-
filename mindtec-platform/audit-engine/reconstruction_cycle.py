"""Build a coherent local reconstruction cycle; publish nothing and preserve prior acceptances."""
import argparse,base64,copy,os,re,sys
from pathlib import Path
import engine,collection_watch,supervisor,integrated_reconstruction as projection,integrated_report
import numeric_distribution_run,shelf_share_run,cold_share_run,declared_availability_run
import declared_pop_run,cold_conversion_run,weighted_inputs_run

VERSION='reconstruction-cycle/1.0.0'
ROOT=Path(__file__).resolve().parent
INPUTS={'shelf_rules','cold_rules','availability_scope','availability_definition','pop_scope','pop_definition','conversion_scope','conversion_definition','weighted_definition','weighted_bindings'}
KINDS={'distribution':'declared_numeric_distribution','shelf':'declared_shelf_share','cold':'declared_cold_share','availability':'declared_company_availability','pop':'declared_owner_pop','conversion':'declared_cold_conversion','weighted':'weighted_input_readiness','projection':'integrated_reconstruction'}
NAMES=['category_eligibility.py','cold_conversion.py','cold_conversion_run.py','cold_share.py','cold_share_run.py','collection_adapter.py','collection_audit.py','collection_watch.py','declared_availability.py','declared_availability_run.py','declared_pop.py','declared_pop_run.py','engine.py','flat_answers.py','integrated_availability.py','integrated_conversion.py','integrated_pop.py','integrated_reconstruction.py','integrated_report.py','integrated_transport.py','invoice_adapter.py','numeric_distribution.py','numeric_distribution_run.py','other_faces.py','perfect_store.py','perfect_store_admission.py','perfect_store_check.py','purchase_binding.py','reconstruction_cycle.py','shelf_share.py','shelf_share_run.py','supervisor.py','weighted_inputs.py','weighted_inputs_run.py','windows_job.py']
LOADED={name:(ROOT/name).read_bytes() for name in NAMES}


def implementation():
 for name,raw in LOADED.items():
  if (ROOT/name).read_bytes()!=raw:raise ValueError('Loaded reconstruction dependency changed: '+name)
 files=copy.deepcopy(LOADED)
 for name in ['integrated_availability_ui.js','integrated_pop_ui.js','integrated_conversion_ui.js']:files[name]=(ROOT/name).read_bytes()
 return engine.code_bundle(files)


def profile(path):
 path=Path(path).resolve();raw=collection_watch.bounded(path,100000);q=engine.load_json_bytes(raw)
 if set(q)!={'schema','version','ps_runtime','runtime','report_dir','inputs'} or q['schema']!='mindtec-reconstruction-cycle/1' or not isinstance(q['version'],str) or not q['version'].strip():raise ValueError('Exact reconstruction cycle profile required')
 for name in ['ps_runtime','runtime','report_dir']:
  if not isinstance(q[name],str) or not Path(q[name]).is_absolute():raise ValueError('Absolute cycle paths required')
 ps,target,reports=[Path(q[k]).resolve() for k in ['ps_runtime','runtime','report_dir']]
 if os.name=='nt' and len(str(target/'cycles'/('f'*64)/'distribution'/'objects'/('f'*64+'.json')))>=260:raise ValueError('Cycle custody path is too long for Windows object links; select a shorter private runtime path')
 if any(a.is_relative_to(b) or b.is_relative_to(a) for a,b in [(ps,target),(ps,reports),(target,reports)]):raise ValueError('Cycle source, custody and reports must be separate')
 if path.is_relative_to(target) or path.is_relative_to(reports):raise ValueError('Cycle profile must be external to output')
 if set(q['inputs'])!=INPUTS:raise ValueError('Complete reconstruction rule inputs required')
 retained={'profile':(raw,'.json')}
 for name,item in q['inputs'].items():
  if set(item)!={'path','sha256'} or not isinstance(item['path'],str) or not Path(item['path']).is_absolute() or not re.fullmatch('[0-9a-f]{64}',str(item['sha256'])):raise ValueError('Exact pinned cycle input required')
  p=Path(item['path']).resolve()
  if p.is_relative_to(target) or p.is_relative_to(reports):raise ValueError('Cycle inputs must remain external')
  data=collection_watch.bounded(p,2000000)
  if engine.sha(data)!=item['sha256']:raise ValueError('Cycle rule input fingerprint differs: '+name)
  retained['input_'+name]=(data if name.endswith(('rules','scope','bindings')) else engine.canonical({'encoding':'base64','original_sha256':engine.sha(data),'content':base64.b64encode(data).decode()}).encode(),'.json')
  if name.endswith(('rules','scope','bindings')):
   parsed=engine.load_json_bytes(data)
   observations=list(parsed.get('observations',[]))
   if parsed.get('absence_rule_evidence'):observations.append(parsed['absence_rule_evidence'])
   for index,observation in enumerate(observations):
    evidence=Path(observation['path'])
    if not evidence.is_absolute() or evidence.resolve().is_relative_to(target) or evidence.resolve().is_relative_to(reports):raise ValueError('External absolute cycle evidence required')
    original=collection_watch.bounded(evidence,2000000)
    if engine.sha(original)!=observation.get('sha256'):raise ValueError('Cycle questionnaire evidence fingerprint differs: '+name)
    retained['evidence_'+name+'_'+str(index)]=(engine.canonical({'encoding':'base64','original_sha256':engine.sha(original),'content':base64.b64encode(original).decode()}).encode(),'.json')
 return q,raw,retained


def stage(root,name,ps):
 cut=projection.captured(root/name,KINDS[name]);r=cut['result']
 source=r['sources']['perfect_store'] if name=='projection' else {'run_id':r.get('source_ps_run_id'),'snapshot_sha256':r.get('source_ps_snapshot_sha256')}
 if any(source[k]!=ps['meta'][k] for k in ['run_id','snapshot_sha256']):raise ValueError('Cycle stage source changed or differs: '+name)
 return cut


def verified(runtime,run_id=None):
 root=Path(runtime).resolve()
 if not (root/'audit.sqlite').is_file():return None
 with engine.Engine(root) as e:
  e.verify();row=e.db.execute("SELECT * FROM runs WHERE json_extract(rules_json,'$.kind')='reconstruction_cycle' AND (? IS NULL OR id=?) ORDER BY at DESC,id DESC LIMIT 1",(run_id,run_id)).fetchone()
  if row is None:return None
  result=engine.load_json_bytes(collection_watch.object_bytes(e,row['snapshot_hash']));rules=engine.load_json_bytes(row['rules_json'].encode())
  for sha in rules['reference_sources'].values():collection_watch.object_bytes(e,sha)
  for name,s in result['stages'].items():
   path=Path(s['runtime']).resolve()
   if path!=root/'cycles'/result['context_sha256']/name:raise ValueError('Cycle stage custody path differs')
   if not (path/'audit.sqlite').is_file():raise ValueError('Accepted cycle stage custody missing')
   with engine.Engine(path) as source:
    source.verify();execution=source.db.execute('SELECT snapshot_hash,rules_json FROM runs WHERE id=?',(s['run_id'],)).fetchone()
    if not execution or execution['snapshot_hash']!=s['snapshot_sha256'] or engine.load_json_bytes(execution['rules_json'].encode())['kind']!=KINDS[name]:raise ValueError('Accepted cycle stage execution differs')
    if collection_watch.object_bytes(source,s['snapshot_sha256'])!=collection_watch.object_bytes(e,rules['reference_sources']['stage_'+name]):raise ValueError('Accepted cycle stage result differs')
  report=Path(result['report']['path']);blob=engine.load_json_bytes(collection_watch.object_bytes(e,rules['reference_sources']['report']));retained=base64.b64decode(blob['content'],validate=True)
  if blob['sha256']!=result['report']['sha256'] or engine.sha(retained)!=blob['sha256'] or report.read_bytes()!=retained:raise ValueError('Accepted cycle report differs')
  return {'run_id':row['id'],'snapshot_sha256':row['snapshot_hash'],'result':result,'custody_verified':True}


def _execute(profile_path,expected_profile=None):
 q,raw,refs=profile(profile_path)
 if expected_profile is not None and raw!=expected_profile:raise ValueError('Cycle profile changed while acquiring exclusive ownership')
 bundle=implementation();ps=projection.captured(q['ps_runtime'],'operational_perfect_store',True)
 source={k:ps['meta'][k] for k in ['run_id','snapshot_sha256']};series=engine.sha(str(Path(profile_path).resolve()));context=engine.sha(engine.canonical({'source':source,'profile_sha256':engine.sha(raw),'implementation_sha256':engine.sha(bundle)}));target=Path(q['runtime']).resolve();prior=verified(target)
 if prior is not None:
  if prior['result']['series']!=series:raise ValueError('Cycle custody belongs to a different profile')
  if prior['result']['context_sha256']==context:
   fresh=projection.captured(q['ps_runtime'],'operational_perfect_store',True)
   if any(fresh['meta'][k]!=source[k] for k in source) or profile(profile_path)[1]!=raw or implementation()!=bundle:raise ValueError('Cycle context changed during verification')
   return {**{k:v for k,v in prior.items() if k!='result'},'reused':True,'report':prior['result']['report']}
 root=target/'cycles'/context;paths={k:Path(v['path']) for k,v in q['inputs'].items()};hashes={k:v['sha256'] for k,v in q['inputs'].items()};cuts={}
 numeric_distribution_run.execute(q['ps_runtime'],root/'distribution');cuts['distribution']=stage(root,'distribution',ps)
 shelf_share_run.execute(root/'distribution',root/'shelf',paths['shelf_rules']);cuts['shelf']=stage(root,'shelf',ps)
 cold_share_run.execute(root/'distribution',root/'cold',paths['cold_rules']);cuts['cold']=stage(root,'cold',ps)
 declared_availability_run.execute(root/'distribution',root/'availability',paths['availability_definition'],hashes['availability_definition'],paths['availability_scope']);cuts['availability']=stage(root,'availability',ps)
 declared_pop_run.execute(q['ps_runtime'],root/'pop',paths['pop_scope'],paths['pop_definition'],hashes['pop_definition']);cuts['pop']=stage(root,'pop',ps)
 cold_conversion_run.execute(root/'distribution',root/'cold',root/'conversion',paths['conversion_scope'],paths['conversion_definition'],hashes['conversion_definition']);cuts['conversion']=stage(root,'conversion',ps)
 weighted_inputs_run.execute(root/'shelf',root/'conversion',root/'weighted',paths['weighted_definition'],hashes['weighted_definition'],paths['weighted_bindings']);cuts['weighted']=stage(root,'weighted',ps)
 projection.execute(q['ps_runtime'],root/'distribution',root/'shelf',root/'projection',root/'cold',root/'availability',root/'pop',root/'conversion');cuts['projection']=stage(root,'projection',ps)
 fresh=projection.captured(q['ps_runtime'],'operational_perfect_store',True)
 if any(fresh['meta'][k]!=source[k] for k in source):raise ValueError('Perfect Store acceptance changed while reconstructing; cycle not promoted')
 if profile(profile_path)[1]!=raw or implementation()!=bundle:raise ValueError('Profile or implementation changed while reconstructing; cycle not promoted')
 # Incomplete stages remain isolated by context; only a complete coherent manifest is accepted.
 reports=Path(q['report_dir']);reports.mkdir(parents=True,exist_ok=True);report=reports/(context+'.html')
 if report.exists():
  import uuid
  report=reports/(context+'-recovery-'+uuid.uuid4().hex+'.html')
 integrated_report.export(root/'projection',report,cuts['projection']['meta']['run_id']);report_raw=report.read_bytes();report_hash=engine.sha(report_raw)
 fresh=projection.captured(q['ps_runtime'],'operational_perfect_store',True)
 if any(fresh['meta'][k]!=source[k] for k in source) or profile(profile_path)[1]!=raw or implementation()!=bundle:raise ValueError('Source or rule context changed during report export; cycle not promoted')
 result={'schema':'mindtec-reconstruction-cycle-result/1','version':VERSION,'series':series,'context_sha256':context,'source_perfect_store':source,'profile_sha256':engine.sha(raw),'implementation_sha256':engine.sha(bundle),'stages':{name:{'runtime':str(root/name),**cut['meta']} for name,cut in cuts.items()},'report':{'path':str(report),'sha256':report_hash},'network_delivery':False,'limits':['Local reconstruction and custody only; no external download or publication.','Unknown inputs and missing official rules remain pending, including official weighted distribution.','A coherent cycle is not proof of field truth or a fraud decision.']}
 refs.update({'implementation':(bundle,'.json'),'source_ps':(ps['raw'],'.json'),'source_ps_execution':(ps['execution'],'.json'),'report':(engine.canonical({'encoding':'base64','sha256':report_hash,'content':base64.b64encode(report_raw).decode()}).encode(),'.json'),**{'stage_'+name:(cut['raw'],'.json') for name,cut in cuts.items()}})
 rules={'kind':'reconstruction_cycle','version':VERSION,'reference_sources':{k:engine.sha(v[0]) for k,v in refs.items()}};summary={'source_ps_run_id':source['run_id'],'completed_stages':len(cuts),'network_delivery':False}
 with engine.Engine(target) as e:run=e.record_result(engine.canonical(result).encode(),ps['policy'],rules,[],summary,refs);e.verify()
 accepted=verified(target,run['run_id']);return {**{k:v for k,v in accepted.items() if k!='result'},'reused':False,'report':result['report']}


def execute(profile_path):
 q,raw,_=profile(profile_path)
 with supervisor.exclusive(Path(q['runtime'])/'reconstruction-cycle.lock'):
  return _execute(profile_path,raw)


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--profile',required=True,type=Path);a=p.parse_args();print(engine.canonical(execute(a.profile)))
