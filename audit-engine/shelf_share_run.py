"""Reconstruct shelf share from retained observer-accepted PS provenance; no network."""
from pathlib import Path
import argparse,base64,collections,re
import engine,collection_watch,perfect_store_admission as admission,perfect_store_check,shelf_share
ROOT=Path(__file__).resolve().parent

def execute(provenance_runtime,runtime,other_rules_path=None):
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
   other_rules=None;mapping_references={}
   if other_rules_path is not None:
    config_path=Path(other_rules_path).resolve()
    if config_path.is_relative_to(destination):raise ValueError('Layout configuration must be outside custody')
    config_raw=collection_watch.bounded(config_path,100000);other_rules=engine.load_json_bytes(config_raw)
    if other_rules.get('schema')!='mindtec-other-face-layouts/1' or other_rules.get('detailed_workbook_sha256')!=ps['source_sha256'] or not isinstance(other_rules.get('version'),str) or not other_rules['version'].strip() or not isinstance(other_rules.get('forms'),dict):raise ValueError('Source-bound layout contract required')
    allowed={'direct_parent_faces','first_child_by_parent_index_then_explicit_paths'}
    if not other_rules['forms'] or any(not isinstance(v,dict) or v.get('layout') not in allowed for v in other_rules['forms'].values()):raise ValueError('Explicit supported per-form layout required')
    observed=set()
    for i,observation in enumerate(other_rules.get('observations',[])):
     path=Path(observation['path'])
     if not path.is_absolute() or path.resolve().is_relative_to(destination) or observation.get('form') not in other_rules['forms']:raise ValueError('External per-form observation required')
     raw_observation=collection_watch.bounded(path,2000000)
     if not re.fullmatch('[0-9a-f]{64}',observation.get('sha256','')) or engine.sha(raw_observation)!=observation['sha256']:raise ValueError('Layout observation fingerprint differs')
     envelope=engine.canonical({'schema':'mindtec-retained-layout-observation/1','encoding':'base64','original_sha256':engine.sha(raw_observation),'content':base64.b64encode(raw_observation).decode('ascii')}).encode();mapping_references['other_layout_observation_'+str(i+1)]=(envelope,'.json');observed.add(observation['form'])
    if observed!=set(other_rules['forms']):raise ValueError('Each configured form needs retained layout evidence')
    mapping_references['other_layout_configuration']=(config_raw,'.json')
   result=shelf_share.evaluate(prepared['flat'],prepared['catalog'],cohort,ps['eligibility_checks'],ps['answer_evidence'],ps['cells'],other_rules);result.update(source_ps_run_id=nd['source_ps_run_id'],source_ps_snapshot_sha256=engine.sha(ps_raw),other_face_layout_version=other_rules['version'] if other_rules else None)
  finally:e.db.execute('ROLLBACK')
 findings=[];auxiliary={}
 for row in result['category_inventories']:
  for observation in row.get('unattributed_auxiliary_observations',[]):
   key=observation['cell_id'];entry=auxiliary.setdefault(key,{'cell_id':key,'kobo_id':row['kobo_id'],'month':row['month'],'affected_categories':set(),'candidate_routes':set(),'answer_ids':set()});entry['affected_categories'].add(row['category']);entry['candidate_routes'].update(observation['candidate_routes']);entry['answer_ids'].update(aid for aid in row['answer_ids'] if key in result['answer_evidence'][aid]['cell_ids'])
  if row['state']!='pending':continue
  evidence={'source_sha256':result['source_sha256'],'kobo_id':row['kobo_id'],'month':row['month'],'category':row['category'],'signals':row['signals'],'answer_ids':row['answer_ids']};f={'rule':'incomplete_shelf_category_denominator','rule_version':shelf_share.VERSION,'severity':'medium','title':'Denominador de estante pendiente de revision','evidence':evidence,'explanation':'La enumeracion o los conteos no permiten un total de categoria completo. Conservar subtotales y originales; no imputar caras ni atribuir fraude.','disposition':'needs_human_review'};f['fingerprint']=engine.sha(engine.canonical({'rule':f['rule'],'version':f['rule_version'],'evidence':evidence}));findings.append(f)
 for key,entry in sorted(auxiliary.items()):
  evidence={'source_sha256':result['source_sha256'],**{k:sorted(v) if isinstance(v,set) else v for k,v in entry.items()}};f={'rule':'shared_auxiliary_name_not_attributed','rule_version':shelf_share.VERSION,'severity':'info','title':'Nombre compartido sin asignacion inequivoca','evidence':evidence,'explanation':'La celda de texto puede corresponder a varias rutas. Se conserva sin asignarla a una marca o categoria y sin crear una fila extra fuera de la enumeracion confirmada. No bloquea los conteos de caras resueltos ni equivale a revision humana favorable.','disposition':'source_mapping_unresolved_nonblocking'};f['fingerprint']=engine.sha(engine.canonical({'rule':f['rule'],'version':f['rule_version'],'evidence':evidence}));findings.append(f)
 names=['engine.py','invoice_adapter.py','collection_adapter.py','collection_audit.py','collection_watch.py','supervisor.py','windows_job.py','flat_answers.py','category_eligibility.py','perfect_store.py','perfect_store_check.py','perfect_store_admission.py','other_faces.py','shelf_share.py'];bundle=engine.code_bundle({n:(ROOT/n).read_bytes() for n in names}|{'reconstruction_runner.py':Path(__file__).read_bytes()});references={'source_ps_result':(ps_raw,'.json'),'source_ps_execution':(metadata_raw,'.json'),'source_ps_implementation':(ps_implementation,'.json'),'admission_manifest':(manifest,'.json'),'implementation':(bundle,'.json'),**mapping_references,**{k:(v,'.xlsx' if k.endswith('workbook') else '.json') for k,v in source_bytes.items()}}
 summary={'monthly_results':len(result['monthly']),'monthly_states':dict(collections.Counter(s['state'] for s in result['monthly'])),'annual_observed_results':len(result['annual_observed_months']),'store_rows':len(result['stores']),'category_inventories':len(result['category_inventories']),'category_findings':sum(f['severity']!='info' for f in findings),'unattributed_auxiliary_cells':len(auxiliary),'source_ps_checks':checks,'network_delivery':False};rule_manifest={'kind':'declared_shelf_share','version':shelf_share.VERSION,'reference_sources':{k:engine.sha(v[0]) for k,v in references.items()}}
 with engine.Engine(destination) as e:
  accepted=e.record_result(engine.canonical(result).encode(),prepared['policy'],rule_manifest,findings,summary,references);head=e.verify()
 return {'run_id':accepted['run_id'],'snapshot':accepted['snapshot'],'ledger_head':head,'summary':summary}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--provenance-runtime',required=True,type=Path);p.add_argument('--runtime',required=True,type=Path);p.add_argument('--other-rules',type=Path);a=p.parse_args();print(engine.canonical(execute(a.provenance_runtime,a.runtime,a.other_rules)))
