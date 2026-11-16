"""Reconstruct shelf share from retained observer-accepted PS provenance; no network."""
from pathlib import Path
import argparse,collections
import engine,collection_watch,perfect_store_admission as admission,perfect_store_check,shelf_share
ROOT=Path(__file__).resolve().parent

def execute(provenance_runtime,runtime):
 source=Path(provenance_runtime).resolve();destination=Path(runtime).resolve()
 if source.is_relative_to(destination) or destination.is_relative_to(source):raise ValueError('Separate source and shelf custody required')
 if not (source/'audit.sqlite').is_file():raise ValueError('Existing provenance custody required')
 with engine.Engine(source) as e:
  e.db.execute('BEGIN')
  try:
   source_head=e.verify();run=e.db.execute("SELECT * FROM runs WHERE json_extract(rules_json,'$.kind')='declared_numeric_distribution' ORDER BY at DESC,id DESC LIMIT 1").fetchone()
   if run is None:raise ValueError('Retained distribution provenance required')
   rules=engine.load_json_bytes(run['rules_json'].encode());nd=engine.load_json_bytes(collection_watch.object_bytes(e,run['snapshot_hash']));refs=rules['reference_sources'];ps_raw=collection_watch.object_bytes(e,refs['source_ps_result']);ps=engine.load_json_bytes(ps_raw);metadata_raw=collection_watch.object_bytes(e,refs['source_ps_execution']);metadata=engine.load_json_bytes(metadata_raw);ps_implementation=collection_watch.object_bytes(e,refs['source_ps_implementation'])
   if metadata['run']['id']!=nd['source_ps_run_id'] or metadata['accepted_event']['payload']['run_id']!=nd['source_ps_run_id'] or engine.sha(ps_raw)!=nd['source_ps_snapshot_sha256']:raise ValueError('Observer-accepted source binding differs')
   source_bytes={k:collection_watch.object_bytes(e,refs['source_ps_'+k]) for k in admission.SOURCE_LIMITS};manifest=collection_watch.object_bytes(e,refs['source_ps_admission_manifest']);a=admission.contract(manifest,destination,destination.parent/'reports');prepared=admission.prepare(a,source_bytes);checks={**perfect_store_check.verify_model(ps),**perfect_store_check.verify_cells(ps,prepared['detailed_book'])};excluded={str(x['id']) for x in prepared['policy']['exclusions']};cohort=[(r['id'],r['month']) for r in prepared['flat'].records if r['id'] not in excluded]
   result=shelf_share.evaluate(prepared['flat'],prepared['catalog'],cohort,ps['eligibility_checks'],ps['answer_evidence'],ps['cells']);result.update(source_ps_run_id=nd['source_ps_run_id'],source_ps_snapshot_sha256=engine.sha(ps_raw))
  finally:e.db.execute('ROLLBACK')
 findings=[]
 for row in result['category_inventories']:
  if row['state']!='pending':continue
  evidence={'source_sha256':result['source_sha256'],'kobo_id':row['kobo_id'],'month':row['month'],'category':row['category'],'signals':row['signals'],'answer_ids':row['answer_ids']};f={'rule':'incomplete_shelf_category_denominator','rule_version':shelf_share.VERSION,'severity':'medium','title':'Denominador de estante pendiente de revision','evidence':evidence,'explanation':'La enumeracion o los conteos no permiten un total de categoria completo. Conservar subtotales y originales; no imputar caras ni atribuir fraude.','disposition':'needs_human_review'};f['fingerprint']=engine.sha(engine.canonical({'rule':f['rule'],'version':f['rule_version'],'evidence':evidence}));findings.append(f)
 names=['engine.py','invoice_adapter.py','collection_adapter.py','collection_audit.py','collection_watch.py','supervisor.py','windows_job.py','flat_answers.py','category_eligibility.py','perfect_store.py','perfect_store_check.py','perfect_store_admission.py','shelf_share.py'];bundle=engine.code_bundle({n:(ROOT/n).read_bytes() for n in names}|{'reconstruction_runner.py':Path(__file__).read_bytes()});references={'source_ps_result':(ps_raw,'.json'),'source_ps_execution':(metadata_raw,'.json'),'source_ps_implementation':(ps_implementation,'.json'),'admission_manifest':(manifest,'.json'),'implementation':(bundle,'.json'),**{k:(v,'.xlsx' if k.endswith('workbook') else '.json') for k,v in source_bytes.items()}}
 summary={'monthly_results':len(result['monthly']),'monthly_states':dict(collections.Counter(s['state'] for s in result['monthly'])),'annual_observed_results':len(result['annual_observed_months']),'store_rows':len(result['stores']),'category_inventories':len(result['category_inventories']),'category_findings':len(findings),'source_ps_checks':checks,'network_delivery':False};rule_manifest={'kind':'declared_shelf_share','version':shelf_share.VERSION,'reference_sources':{k:engine.sha(v[0]) for k,v in references.items()}}
 with engine.Engine(destination) as e:
  accepted=e.record_result(engine.canonical(result).encode(),prepared['policy'],rule_manifest,findings,summary,references);head=e.verify()
 return {'run_id':accepted['run_id'],'snapshot':accepted['snapshot'],'ledger_head':head,'summary':summary}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--provenance-runtime',required=True,type=Path);p.add_argument('--runtime',required=True,type=Path);a=p.parse_args();print(engine.canonical(execute(a.provenance_runtime,a.runtime)))
