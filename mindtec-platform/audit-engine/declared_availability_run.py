"""Reconstruct declared company availability from retained observer-accepted PS provenance; no network."""
from pathlib import Path
import argparse,base64,collections,re
import engine,collection_watch,perfect_store_admission as admission,perfect_store_check,declared_availability
ROOT=Path(__file__).resolve().parent

def execute(provenance_runtime,runtime,definition_path=None,definition_sha256=None,question_universe_path=None):
 source=Path(provenance_runtime).resolve();destination=Path(runtime).resolve()
 if source.is_relative_to(destination) or destination.is_relative_to(source):raise ValueError('Separate source and availability custody required')
 if not (source/'audit.sqlite').is_file():raise ValueError('Existing provenance custody required')
 with engine.Engine(source) as e:
  e.db.execute('BEGIN')
  try:
   source_head=e.verify();run=e.db.execute("SELECT * FROM runs WHERE json_extract(rules_json,'$.kind')='declared_numeric_distribution' ORDER BY at DESC,id DESC LIMIT 1").fetchone()
   if run is None:raise ValueError('Retained distribution provenance required')
   rules=engine.load_json_bytes(run['rules_json'].encode());nd=engine.load_json_bytes(collection_watch.object_bytes(e,run['snapshot_hash']));refs=rules['reference_sources'];ps_raw=collection_watch.object_bytes(e,refs['source_ps_result']);ps=engine.load_json_bytes(ps_raw);metadata_raw=collection_watch.object_bytes(e,refs['source_ps_execution']);metadata=engine.load_json_bytes(metadata_raw);ps_implementation=collection_watch.object_bytes(e,refs['source_ps_implementation'])
   if metadata['run']['id']!=nd['source_ps_run_id'] or metadata['accepted_event']['payload']['run_id']!=nd['source_ps_run_id'] or engine.sha(ps_raw)!=nd['source_ps_snapshot_sha256']:raise ValueError('Observer-accepted source binding differs')
   source_bytes={k:collection_watch.object_bytes(e,refs['source_ps_'+k]) for k in admission.SOURCE_LIMITS};manifest=collection_watch.object_bytes(e,refs['source_ps_admission_manifest']);a=admission.contract(manifest,destination,destination.parent/'reports');prepared=admission.prepare(a,source_bytes);checks={**perfect_store_check.verify_model(ps),**perfect_store_check.verify_cells(ps,prepared['detailed_book'])};excluded={str(x['id']) for x in prepared['policy']['exclusions']};cohort=[(r['id'],r['month']) for r in prepared['flat'].records if r['id'] not in excluded]
   if ps['source_sha256']!=engine.sha(source_bytes['detailed_workbook']) or ps['catalogue_source_sha256']!=engine.sha(source_bytes['normalized_result_workbook']) or ps['configuration_version']!=prepared['configuration']['version'] or engine.canonical(prepared['policy'])!=metadata['run']['policy_json']:raise ValueError('Availability source scope differs')
   definition_refs={}
   if (definition_path is None)!=(definition_sha256 is None):raise ValueError('Definition path and SHA must be supplied together')
   if definition_path is not None:
    path=Path(definition_path).resolve()
    if path.is_relative_to(destination):raise ValueError('Definition evidence must be outside custody')
    evidence=collection_watch.bounded(path,2000000)
    if not re.fullmatch('[0-9a-f]{64}',definition_sha256) or engine.sha(evidence)!=definition_sha256:raise ValueError('Definition evidence hash differs')
    wrapped=engine.canonical({'schema':'mindtec-retained-definition/1','encoding':'base64','original_sha256':engine.sha(evidence),'content':base64.b64encode(evidence).decode()}).encode();definition_refs['observed_definition']=(wrapped,'.json')
   question_scope=None
   if question_universe_path is not None:
    qpath=Path(question_universe_path).resolve()
    if qpath.is_relative_to(destination):raise ValueError('Question universe must be outside custody')
    qraw=collection_watch.bounded(qpath,100000);question_scope=engine.load_json_bytes(qraw);observed=set()
    if not isinstance(question_scope.get('forms'),dict):raise ValueError('Explicit per-form question universe required')
    for index,item in enumerate(question_scope.get('observations',[])):
     path=Path(item['path'])
     if not path.is_absolute() or path.resolve().is_relative_to(destination) or item.get('form') not in question_scope['forms']:raise ValueError('External questionnaire observation required')
     raw=collection_watch.bounded(path,2000000)
     if not re.fullmatch('[0-9a-f]{64}',item.get('sha256','')) or engine.sha(raw)!=item['sha256']:raise ValueError('Questionnaire observation hash differs')
     wrapped=engine.canonical({'schema':'mindtec-retained-question-universe/1','encoding':'base64','original_sha256':engine.sha(raw),'content':base64.b64encode(raw).decode()}).encode();definition_refs['question_universe_observation_'+str(index+1)]=(wrapped,'.json');observed.add(item['form'])
    if observed!=set(question_scope['forms']):raise ValueError('Each admitted questionnaire universe needs evidence')
    definition_refs['question_universe_configuration']=(qraw,'.json')
   result=declared_availability.evaluate(prepared['flat'],prepared['catalog'],cohort,prepared['configuration'],question_scope);result.update(source_ps_run_id=nd['source_ps_run_id'],source_ps_snapshot_sha256=engine.sha(ps_raw),definition_evidence_sha256=definition_sha256)
   availability_checks=perfect_store_check.verify_cells(result,prepared['detailed_book'])
  finally:e.db.execute('ROLLBACK')
 findings=[]
 for inv in result['inventories']:
  candidates=[('company_buying_scope',None,inv['scope_signals'],inv['answer_ids'])] if inv['scope_signals'] else []
  candidates += [('company_stockout_declaration',row['company'],row['signals'],row['answer_ids']) for row in inv['stock_rows'] if row['signals']]
  for rule,company,signals,answer_ids in candidates:
   evidence={'source_sha256':result['source_sha256'],'kobo_id':inv['kobo_id'],'month':inv['month'],'company':company,'signals':signals,'answer_ids':answer_ids};f={'rule':rule,'rule_version':declared_availability.VERSION,'severity':'medium','title':'Declaración de empresa o universo por revisar','evidence':evidence,'explanation':'Conservar el universo y las respuestas originales; no convertir vacíos, identidades o contradicciones en disponibilidad confirmada ni atribuir fraude.','disposition':'needs_human_review'};f['fingerprint']=engine.sha(engine.canonical({'rule':rule,'version':f['rule_version'],'evidence':evidence}));findings.append(f)
 findings += declared_availability.ps_scope_findings(ps,result)
 names=['engine.py','invoice_adapter.py','collection_adapter.py','collection_audit.py','collection_watch.py','supervisor.py','windows_job.py','flat_answers.py','category_eligibility.py','perfect_store.py','perfect_store_check.py','perfect_store_admission.py','declared_availability.py'];bundle=engine.code_bundle({n:(ROOT/n).read_bytes() for n in names}|{'reconstruction_runner.py':Path(__file__).read_bytes()});references={'source_ps_result':(ps_raw,'.json'),'source_ps_execution':(metadata_raw,'.json'),'source_ps_implementation':(ps_implementation,'.json'),'admission_manifest':(manifest,'.json'),'implementation':(bundle,'.json'),**definition_refs,**{k:(v,'.xlsx' if k.endswith('workbook') else '.json') for k,v in source_bytes.items()}}
 summary={'monthly_results':len(result['monthly']),'monthly_states':dict(collections.Counter(s['state'] for s in result['monthly'])),'annual_observed_results':len(result['annual_observed_months']),'store_rows':len(result['stores']),'company_inventories':len(result['inventories']),'brand_references':len(result['brand_references']),'unmapped_brand_references':sum(x['company'] is None for x in result['brand_references']),'findings':len(findings),'ps_methodology_findings':sum(f['rule']=='ps_stock_inapplicability_not_supported_by_question_universe' for f in findings),'source_ps_checks':checks,'verified_availability_cells':availability_checks['verified_original_cells'],'network_delivery':False};rule_manifest={'kind':'declared_company_availability','version':declared_availability.VERSION,'reference_sources':{k:engine.sha(v[0]) for k,v in references.items()}}
 with engine.Engine(destination) as e:
  accepted=e.record_result(engine.canonical(result).encode(),prepared['policy'],rule_manifest,findings,summary,references);head=e.verify()
 return {'run_id':accepted['run_id'],'snapshot':accepted['snapshot'],'ledger_head':head,'summary':summary}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--provenance-runtime',required=True,type=Path);p.add_argument('--runtime',required=True,type=Path);p.add_argument('--definition-evidence',type=Path);p.add_argument('--definition-sha256');p.add_argument('--question-universe',type=Path);a=p.parse_args();print(engine.canonical(execute(a.provenance_runtime,a.runtime,a.definition_evidence,a.definition_sha256,a.question_universe)))
