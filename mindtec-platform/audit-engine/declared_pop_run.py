"""Capture source-bound POP reconstruction without network or mutation of live PS."""
import argparse,base64,collections
from pathlib import Path
import engine,collection_watch,perfect_store_admission as admission,perfect_store_check,declared_pop

def execute(ps_runtime,runtime,question_scope,definition_evidence,definition_sha256):
 source=Path(ps_runtime).resolve();target=Path(runtime).resolve()
 if source.is_relative_to(target) or target.is_relative_to(source) or not (source/'audit.sqlite').is_file():raise ValueError('Existing separate accepted PS custody required')
 def read_external(path,limit):
  path=Path(path).resolve()
  if path.is_relative_to(target):raise ValueError('POP inputs must be outside output custody')
  return collection_watch.bounded(path,limit)
 scope_raw=read_external(question_scope,100000);scope=engine.load_json_bytes(scope_raw);definition=read_external(definition_evidence,2000000)
 if engine.sha(definition)!=definition_sha256:raise ValueError('Observed POP definition hash differs')
 observed=set();observations={}
 for i,item in enumerate(scope.get('observations',[])):
  if item.get('form') not in scope.get('forms',{}) or not Path(item['path']).is_absolute():raise ValueError('Per-form original POP observations required')
  raw=read_external(item['path'],2000000)
  if engine.sha(raw)!=item['sha256']:raise ValueError('Observed POP question choices hash differs')
  observations['question_observation_'+str(i+1)]=(engine.canonical({'schema':'mindtec-retained-pop-observation/1','form':item['form'],'original_sha256':engine.sha(raw),'encoding':'base64','content':base64.b64encode(raw).decode()}).encode(),'.json');observed.add(item['form'])
 if not scope.get('forms') or observed!=set(scope['forms']):raise ValueError('Every POP form needs retained questionnaire observations')
 if scope.get('unselected_owner_policy')=='confirmed_absence_in_answered_pop_section':
  item=scope.get('absence_rule_evidence',{});path=Path(item.get('path',''))
  if not path.is_absolute():raise ValueError('Retained user POP absence decision required')
  raw=read_external(path,100000)
  if engine.sha(raw)!=item.get('sha256'):raise ValueError('User POP absence decision hash differs')
  observations['absence_rule_evidence']=(engine.canonical({'schema':'mindtec-retained-pop-business-rule/1','original_sha256':engine.sha(raw),'encoding':'base64','content':base64.b64encode(raw).decode()}).encode(),'.json')
 with engine.Engine(source) as e:
  e.db.execute('BEGIN')
  try:
   head=e.verify();event=None
   for row in e.db.execute('SELECT event_json FROM events ORDER BY seq DESC'):
    candidate=engine.load_json_bytes(row[0].encode())
    if candidate['action']=='perfect_store.observer.accepted':event=candidate;break
   if event is None:raise ValueError('Observer-accepted PS execution required')
   run=e.db.execute('SELECT * FROM runs WHERE id=?',(event['payload']['run_id'],)).fetchone()
   if run is None:raise ValueError('Accepted PS execution missing')
   rules=engine.load_json_bytes(run['rules_json'].encode())
   if rules.get('kind')!='operational_perfect_store' or rules.get('context_sha256')!=event['payload']['context_sha256']:raise ValueError('Accepted PS binding differs')
   ps_raw=collection_watch.object_bytes(e,run['snapshot_hash']);ps=engine.load_json_bytes(ps_raw);originals={k:collection_watch.object_bytes(e,h) for k,h in rules['reference_sources'].items()};a=admission.contract(originals['admission_manifest'],target,target.parent/'reports');prepared=admission.prepare(a,{k:originals[k] for k in admission.SOURCE_LIMITS})
   if ps['source_sha256']!=engine.sha(originals['detailed_workbook']) or ps['catalogue_source_sha256']!=engine.sha(originals['normalized_result_workbook']) or ps['configuration_version']!=prepared['configuration']['version'] or engine.canonical(prepared['policy'])!=run['policy_json']:raise ValueError('POP source scope differs')
   checks={**perfect_store_check.verify_model(ps),**perfect_store_check.verify_cells(ps,prepared['detailed_book'])};excluded={str(x['id']) for x in prepared['policy']['exclusions']};cohort=[(r['id'],r['month']) for r in prepared['flat'].records if r['id'] not in excluded]
   result=declared_pop.evaluate(prepared['flat'],prepared['catalog'],cohort,ps,prepared['configuration'],scope);result.update(source_ps_run_id=run['id'],source_ps_snapshot_sha256=run['snapshot_hash'],definition_evidence_sha256=definition_sha256);pop_checks=perfect_store_check.verify_cells(result,prepared['detailed_book']);metadata=engine.canonical({'run':dict(run),'accepted_event':event,'verified_ledger_head':head}).encode()
  finally:e.db.execute('ROLLBACK')
 findings=declared_pop.findings(ps,result);names=['engine.py','invoice_adapter.py','collection_adapter.py','collection_audit.py','collection_watch.py','supervisor.py','windows_job.py','flat_answers.py','category_eligibility.py','perfect_store.py','perfect_store_check.py','perfect_store_admission.py','numeric_distribution.py','declared_pop.py',Path(__file__).name];bundle=engine.code_bundle({n:Path(__file__).with_name(n).read_bytes() for n in names})
 refs={'source_ps_result':(ps_raw,'.json'),'source_ps_execution':(metadata,'.json'),'implementation':(bundle,'.json'),'question_scope':(scope_raw,'.json'),'observed_definition':(engine.canonical({'schema':'mindtec-retained-pop-definition/1','encoding':'base64','original_sha256':definition_sha256,'content':base64.b64encode(definition).decode()}).encode(),'.json'),**observations,**{'source_ps_'+k:(v,'.xlsx' if k.endswith('workbook') else '.json') for k,v in originals.items()}}
 manifest={'kind':'declared_owner_pop','version':declared_pop.VERSION,'reference_sources':{k:engine.sha(v[0]) for k,v in refs.items()}};summary={'monthly_results':len(result['monthly']),'annual_observed_results':len(result['annual_observed_months']),'monthly_states':dict(collections.Counter(r['state'] for r in result['monthly'])),'stores':len(result['stores']),'company_rows':len(result['company_rows']),'findings':len(findings),'ps_dependency_findings':sum(f['rule']=='ps_pop_company_scope_not_supported' for f in findings),'verified_original_cells':pop_checks['verified_original_cells'],'ps_checks':checks,'network_delivery':False}
 with engine.Engine(target) as e:accepted=e.record_result(engine.canonical(result).encode(),prepared['policy'],manifest,findings,summary,refs);head=e.verify()
 return {'run_id':accepted['run_id'],'snapshot_sha256':accepted['snapshot'],'ledger_head':head,'summary':summary}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['ps-runtime','runtime','question-scope','definition-evidence']:p.add_argument('--'+name,required=True,type=Path)
 p.add_argument('--definition-sha256',required=True);a=p.parse_args();print(engine.canonical(execute(a.ps_runtime,a.runtime,a.question_scope,a.definition_evidence,a.definition_sha256)))
