"""Retain declared distribution using the last observer-accepted PS execution."""
import argparse,collections
from pathlib import Path
import engine,collection_watch,perfect_store_admission,perfect_store_check,numeric_distribution

def execute(ps_runtime,runtime):
 source=Path(ps_runtime).resolve();runtime=Path(runtime).resolve()
 if source.is_relative_to(runtime) or runtime.is_relative_to(source):raise ValueError('Distribution custody must be separate from Perfect Store custody')
 if not (source/'audit.sqlite').is_file():raise ValueError('Existing Perfect Store custody required')
 with engine.Engine(source) as e:
  e.db.execute('BEGIN')
  try:
   source_head=e.verify();event=None
   for row in e.db.execute('SELECT event_json FROM events ORDER BY seq DESC'):
    candidate=engine.load_json_bytes(row[0].encode())
    if candidate['action']=='perfect_store.observer.accepted':event=candidate;break
   if event is None:raise ValueError('Observer-accepted Perfect Store execution required')
   accepted=event['payload'];run=e.db.execute('SELECT * FROM runs WHERE id=?',(accepted['run_id'],)).fetchone()
   if run is None:raise ValueError('Accepted source execution missing')
   rules=engine.load_json_bytes(run['rules_json'].encode());raw=collection_watch.object_bytes(e,run['snapshot_hash']);ps=engine.load_json_bytes(raw)
   if rules.get('kind')!='operational_perfect_store' or rules.get('context_sha256')!=accepted['context_sha256']:raise ValueError('Accepted source binding differs')
   refs=rules['reference_sources'];source_bytes={k:collection_watch.object_bytes(e,d) for k,d in refs.items()};a=perfect_store_admission.contract(source_bytes['admission_manifest'],runtime,runtime.parent/'reports')
   captured={k:source_bytes[k] for k in perfect_store_admission.SOURCE_LIMITS};prepared=perfect_store_admission.prepare(a,captured)
   if ps['source_sha256']!=engine.sha(captured['detailed_workbook']) or ps['catalogue_source_sha256']!=engine.sha(captured['normalized_result_workbook']) or ps['configuration_version']!=prepared['configuration']['version'] or engine.canonical(prepared['policy'])!=run['policy_json']:raise ValueError('Derived distribution source scope differs')
   checks={**perfect_store_check.verify_model(ps),**perfect_store_check.verify_cells(ps,prepared['detailed_book'])};excluded={str(x['id']) for x in prepared['policy']['exclusions']};cohort=[(r['id'],r['month']) for r in prepared['flat'].records if r['id'] not in excluded]
   result=numeric_distribution.evaluate(ps,prepared['catalog'],cohort);result.update(source_ps_run_id=run['id'],source_ps_snapshot_sha256=run['snapshot_hash'],source_ps_ledger_head=source_head,admission_version=a['version'])
   metadata=engine.canonical({'run':dict(run),'accepted_event':event,'verified_ledger_head':source_head}).encode()
  finally:e.db.execute('ROLLBACK')
 names=['engine.py','invoice_adapter.py','collection_adapter.py','collection_audit.py','collection_watch.py','supervisor.py','windows_job.py','flat_answers.py','category_eligibility.py','perfect_store.py','perfect_store_check.py','perfect_store_admission.py','numeric_distribution.py',Path(__file__).name]
 bundle=engine.code_bundle({n:Path(__file__).with_name(n).read_bytes() for n in names})
 references={'source_ps_result':(raw,'.json'),'source_ps_execution':(metadata,'.json'),'implementation':(bundle,'.json'),**{'source_ps_'+k:(v,'.xlsx' if k.endswith('workbook') else '.json') for k,v in source_bytes.items()}}
 manifest={'kind':'declared_numeric_distribution','version':numeric_distribution.VERSION,'source_ps_run_id':result['source_ps_run_id'],'reference_sources':{k:engine.sha(v[0]) for k,v in references.items()}}
 summary={'monthly_results':len(result['monthly']),'annual_observed_results':len(result['annual_observed_months']),'states':dict(collections.Counter(s['state'] for s in result['monthly'])),'store_rows':len(result['stores']),'source_ps_checks':checks,'network_delivery':False}
 with engine.Engine(runtime) as e:
  accepted=e.record_result(engine.canonical(result).encode(),prepared['policy'],manifest,[],summary,references);head=e.verify()
 return {'run_id':accepted['run_id'],'snapshot_sha256':accepted['snapshot'],'ledger_head':head,'summary':summary}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--ps-runtime',required=True,type=Path);p.add_argument('--runtime',required=True,type=Path);a=p.parse_args();print(engine.canonical(execute(a.ps_runtime,a.runtime)))
