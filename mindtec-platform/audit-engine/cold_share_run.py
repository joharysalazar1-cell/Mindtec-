"""Reconstruct cold share from retained observer-accepted PS provenance; no network."""
from pathlib import Path
import argparse,base64,collections,re
import engine,collection_watch,perfect_store_admission as admission,perfect_store_check,cold_share
ROOT=Path(__file__).resolve().parent

def execute(provenance_runtime,runtime,cooler_rules_path=None):
 source=Path(provenance_runtime).resolve();destination=Path(runtime).resolve()
 if source.is_relative_to(destination) or destination.is_relative_to(source):raise ValueError('Separate source and cold custody required')
 if not (source/'audit.sqlite').is_file():raise ValueError('Existing provenance custody required')
 with engine.Engine(source) as e:
  e.db.execute('BEGIN')
  try:
   source_head=e.verify();run=e.db.execute("SELECT * FROM runs WHERE json_extract(rules_json,'$.kind')='declared_numeric_distribution' ORDER BY at DESC,id DESC LIMIT 1").fetchone()
   if run is None:raise ValueError('Retained distribution provenance required')
   rules=engine.load_json_bytes(run['rules_json'].encode());nd=engine.load_json_bytes(collection_watch.object_bytes(e,run['snapshot_hash']));refs=rules['reference_sources'];ps_raw=collection_watch.object_bytes(e,refs['source_ps_result']);ps=engine.load_json_bytes(ps_raw);metadata_raw=collection_watch.object_bytes(e,refs['source_ps_execution']);metadata=engine.load_json_bytes(metadata_raw);ps_implementation=collection_watch.object_bytes(e,refs['source_ps_implementation'])
   if metadata['run']['id']!=nd['source_ps_run_id'] or metadata['accepted_event']['payload']['run_id']!=nd['source_ps_run_id'] or engine.sha(ps_raw)!=nd['source_ps_snapshot_sha256']:raise ValueError('Observer-accepted source binding differs')
   source_bytes={k:collection_watch.object_bytes(e,refs['source_ps_'+k]) for k in admission.SOURCE_LIMITS};manifest=collection_watch.object_bytes(e,refs['source_ps_admission_manifest']);a=admission.contract(manifest,destination,destination.parent/'reports');prepared=admission.prepare(a,source_bytes);checks={**perfect_store_check.verify_model(ps),**perfect_store_check.verify_cells(ps,prepared['detailed_book'])};excluded={str(x['id']) for x in prepared['policy']['exclusions']};cohort=[(r['id'],r['month']) for r in prepared['flat'].records if r['id'] not in excluded]
   if ps['source_sha256']!=engine.sha(source_bytes['detailed_workbook']) or ps['catalogue_source_sha256']!=engine.sha(source_bytes['normalized_result_workbook']) or ps['configuration_version']!=prepared['configuration']['version'] or engine.canonical(prepared['policy'])!=metadata['run']['policy_json']:raise ValueError('Cold source scope differs')
   cooler_rules=None;scope_refs={}
   if cooler_rules_path is not None:
    rule_path=Path(cooler_rules_path).resolve()
    if rule_path.is_relative_to(destination):raise ValueError('Scope configuration must be outside custody')
    scope_raw=collection_watch.bounded(rule_path,100000);cooler_rules=engine.load_json_bytes(scope_raw);observed=set()
    if not isinstance(cooler_rules.get('forms'),dict):raise ValueError('Explicit per-form cooler scope required')
    for index,item in enumerate(cooler_rules.get('observations',[])):
     path=Path(item['path'])
     if not path.is_absolute() or path.resolve().is_relative_to(destination) or item.get('form') not in cooler_rules['forms']:raise ValueError('External scoped observation required')
     raw=collection_watch.bounded(path,2000000)
     if not re.fullmatch('[0-9a-f]{64}',item.get('sha256','')) or engine.sha(raw)!=item['sha256']:raise ValueError('Scope observation hash differs')
     wrapped=engine.canonical({'schema':'mindtec-retained-scope-observation/1','original_sha256':engine.sha(raw),'encoding':'base64','content':base64.b64encode(raw).decode()}).encode();scope_refs['cooler_scope_observation_'+str(index+1)]=(wrapped,'.json');observed.add(item['form'])
    if observed!=set(cooler_rules['forms']):raise ValueError('Each cooler-scope form needs evidence')
    scope_refs['cooler_scope_configuration']=(scope_raw,'.json')
   result=cold_share.evaluate(prepared['flat'],prepared['catalog'],cohort,ps['eligibility_checks'],ps['answer_evidence'],ps['cells'],cooler_rules);result.update(source_ps_run_id=nd['source_ps_run_id'],source_ps_snapshot_sha256=engine.sha(ps_raw),cooler_scope_version=cooler_rules['version'] if cooler_rules else None)
   cold_checks=perfect_store_check.verify_cells(result,prepared['detailed_book'])
  finally:e.db.execute('ROLLBACK')
 findings=[]
 for row in result['category_inventories']:
  if row['state']!='pending':continue
  evidence={'source_sha256':result['source_sha256'],'kobo_id':row['kobo_id'],'month':row['month'],'category':row['category'],'layout':row['layout'],'signals':row['signals'],'answer_ids':row['answer_ids']};unsupported=row['signals']==['legacy_global_cold_faces_not_category_attributed'];f={'rule':'unresolved_cold_category_denominator','rule_version':cold_share.VERSION,'severity':'info' if unsupported else 'medium','title':'Caras en frío sin denominador completo por categoría','evidence':evidence,'explanation':'La lista global antigua no se reparte entre categorías. Los vacíos y las contradicciones permanecen pendientes. Se conserva evidencia sin imputar caras ni decidir fraude.','disposition':'source_scope_unresolved' if unsupported else 'needs_human_review'};f['fingerprint']=engine.sha(engine.canonical({'rule':f['rule'],'version':f['rule_version'],'evidence':evidence}));findings.append(f)
 names=['engine.py','invoice_adapter.py','collection_adapter.py','collection_audit.py','collection_watch.py','supervisor.py','windows_job.py','flat_answers.py','category_eligibility.py','perfect_store.py','perfect_store_check.py','perfect_store_admission.py','cold_share.py'];bundle=engine.code_bundle({n:(ROOT/n).read_bytes() for n in names}|{'reconstruction_runner.py':Path(__file__).read_bytes()});references={'source_ps_result':(ps_raw,'.json'),'source_ps_execution':(metadata_raw,'.json'),'source_ps_implementation':(ps_implementation,'.json'),'admission_manifest':(manifest,'.json'),'implementation':(bundle,'.json'),**scope_refs,**{k:(v,'.xlsx' if k.endswith('workbook') else '.json') for k,v in source_bytes.items()}}
 summary={'monthly_results':len(result['monthly']),'monthly_states':dict(collections.Counter(s['state'] for s in result['monthly'])),'annual_observed_results':len(result['annual_observed_months']),'store_rows':len(result['stores']),'category_inventories':len(result['category_inventories']),'category_findings':sum(f['severity']!='info' for f in findings),'source_ps_checks':checks,'verified_cold_cells':cold_checks['verified_original_cells'],'network_delivery':False};rule_manifest={'kind':'declared_cold_share','version':cold_share.VERSION,'reference_sources':{k:engine.sha(v[0]) for k,v in references.items()}}
 with engine.Engine(destination) as e:
  accepted=e.record_result(engine.canonical(result).encode(),prepared['policy'],rule_manifest,findings,summary,references);head=e.verify()
 return {'run_id':accepted['run_id'],'snapshot':accepted['snapshot'],'ledger_head':head,'summary':summary}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--provenance-runtime',required=True,type=Path);p.add_argument('--runtime',required=True,type=Path);p.add_argument('--cooler-rules',type=Path);a=p.parse_args();print(engine.canonical(execute(a.provenance_runtime,a.runtime,a.cooler_rules)))
