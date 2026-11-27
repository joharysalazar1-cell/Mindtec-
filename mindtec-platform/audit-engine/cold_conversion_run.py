"""Retain brand/family cold conversion from compatible accepted provenance, no network."""
import argparse,base64,collections,re
from pathlib import Path
import engine,collection_watch,perfect_store_admission as admission,perfect_store_check,cold_conversion

def capture(runtime,kind):
 root=Path(runtime).resolve()
 if not (root/'audit.sqlite').is_file():raise ValueError('Existing source custody required')
 with engine.Engine(root) as e:
  e.db.execute('BEGIN')
  try:
   head=e.verify();run=e.db.execute("SELECT * FROM runs WHERE json_extract(rules_json,'$.kind')=? ORDER BY at DESC,id DESC LIMIT 1",(kind,)).fetchone()
   if run is None:raise ValueError('Required source execution absent')
   rules=engine.load_json_bytes(run['rules_json'].encode());raw=collection_watch.object_bytes(e,run['snapshot_hash']);refs={k:collection_watch.object_bytes(e,h) for k,h in rules['reference_sources'].items()}
   return {'meta':{'run_id':run['id'],'snapshot_sha256':run['snapshot_hash'],'ledger_head':head,'rule_version':rules['version']},'raw':raw,'result':engine.load_json_bytes(raw),'policy':engine.load_json_bytes(run['policy_json'].encode()),'originals':refs,'execution':engine.canonical({'run':dict(run),'verified_head':head}).encode()}
  finally:e.db.execute('ROLLBACK')

def execute(distribution_runtime,cold_runtime,runtime,scope_path,definition_path,definition_sha256):
 source=Path(distribution_runtime).resolve();cold_root=Path(cold_runtime).resolve();target=Path(runtime).resolve()
 if any(target.is_relative_to(p) or p.is_relative_to(target) for p in [source,cold_root]):raise ValueError('Separate conversion custody required')
 def external(path,limit):
  path=Path(path).resolve()
  if path.is_relative_to(target):raise ValueError('Conversion inputs must be outside output custody')
  return collection_watch.bounded(path,limit)
 scope_raw=external(scope_path,100000);scope=engine.load_json_bytes(scope_raw);definition=external(definition_path,2000000)
 if not re.fullmatch('[0-9a-f]{64}',definition_sha256) or engine.sha(definition)!=definition_sha256:raise ValueError('Conversion definition evidence hash differs')
 observations={};seen=set()
 for index,item in enumerate(scope.get('observations',[])):
  if item.get('form') not in scope.get('forms',{}) or not Path(item['path']).is_absolute():raise ValueError('Observed per-form conversion scope required')
  raw=external(item['path'],2000000)
  if engine.sha(raw)!=item.get('sha256'):raise ValueError('Conversion scope observation hash differs')
  observations['scope_observation_'+str(index+1)]=(engine.canonical({'schema':'mindtec-retained-conversion-observation/1','form':item['form'],'encoding':'base64','original_sha256':engine.sha(raw),'content':base64.b64encode(raw).decode()}).encode(),'.json');seen.add(item['form'])
 if not scope.get('forms') or seen!=set(scope['forms']):raise ValueError('Each conversion form needs retained scope evidence')
 nd=capture(source,'declared_numeric_distribution');cold=capture(cold_root,'declared_cold_share');nr=nd['result'];cr=cold['result'];refs=nd['originals']
 if engine.canonical(nd['policy'])!=engine.canonical(cold['policy']):raise ValueError('Conversion source exclusion policies differ')
 ps_raw=refs['source_ps_result'];ps=engine.load_json_bytes(ps_raw);metadata_raw=refs['source_ps_execution'];metadata=engine.load_json_bytes(metadata_raw)
 if metadata['run']['id']!=nr['source_ps_run_id'] or metadata['accepted_event']['payload']['run_id']!=nr['source_ps_run_id'] or engine.sha(ps_raw)!=nr['source_ps_snapshot_sha256'] or cold['originals']['source_ps_result']!=ps_raw:raise ValueError('Conversion observer-accepted source binding differs')
 originals={k:refs['source_ps_'+k] for k in admission.SOURCE_LIMITS};manifest=refs['source_ps_admission_manifest'];a=admission.contract(manifest,target,target.parent/'reports');prepared=admission.prepare(a,originals)
 if ps['source_sha256']!=engine.sha(originals['detailed_workbook']) or ps['catalogue_source_sha256']!=engine.sha(originals['normalized_result_workbook']) or ps['configuration_version']!=prepared['configuration']['version'] or engine.canonical(prepared['policy'])!=metadata['run']['policy_json']:raise ValueError('Conversion admitted source scope differs')
 checks={**perfect_store_check.verify_model(ps),**perfect_store_check.verify_cells(ps,prepared['detailed_book'])};excluded={str(x['id']) for x in prepared['policy']['exclusions']};cohort=[(r['id'],r['month']) for r in prepared['flat'].records if r['id'] not in excluded]
 result=cold_conversion.evaluate(prepared['flat'],prepared['catalog'],cohort,nr,cr,scope);result.update(source_distribution=nd['meta'],source_cold=cold['meta'],definition_evidence_sha256=definition_sha256);cell_checks=perfect_store_check.verify_cells(result,prepared['detailed_book']);findings=[]
 def finding(rule,title,evidence,severity,explanation):
  f={'rule':rule,'rule_version':cold_conversion.VERSION,'severity':severity,'title':title,'evidence':{'source_sha256':result['source_sha256'],**evidence},'explanation':explanation,'disposition':'source_scope_unresolved' if severity=='info' else 'needs_human_review'};f['fingerprint']=engine.sha(engine.canonical(f));findings.append(f)
 for eq in result['equipment']:
  if eq['value'] is not None:continue
  finding('conversion_operating_equipment_unresolved','Base de equipos operativos por resolver',{k:eq[k] for k in ['kobo_id','month','form','total_count','bsa_count','enumerated_count','signals','answer_ids']},'medium','Una enumeración parcial BSA no demuestra que todos los equipos estén apagados. Conservar conteos y respuestas; la presencia en frío no demuestra operación. No se presume fraude.')
 groups=collections.defaultdict(list)
 for row in result['stores']:
  if row['eligible'] is True and row['cold'] is None or any(s in row['signals'] for s in ['cold_presence_without_declared_brand_presence','cold_count_without_operating_equipment']):groups[(row['month'],row['family'],tuple(row['signals']))].append(row)
 for (month,fam,signals),rows in sorted(groups.items()):
  evidence={'month':month,'family':fam,'signals':list(signals),'store_row_ids':[r['id'] for r in rows],'kobo_ids':sorted({r['kobo_id'] for r in rows}),'answer_ids':sorted({aid for r in rows for aid in r['answer_ids']})};informational=all(s in ['legacy_cold_brand_family_ambiguous','other_brand_bucket_not_an_identified_brand','cold_count_without_operating_equipment'] for s in signals)
  finding('conversion_cold_or_presence_scope_unresolved','Declaración de frío o presencia por revisar',evidence,'info' if informational else 'medium','No repartir la lista global entre familias ambiguas ni convertir una falta de respuesta en ausencia. Los conteos de caras y operación de equipos son declaraciones distintas; revisar el alcance sin inferir causalidad, veracidad de campo o fraude.')
 names=['engine.py','invoice_adapter.py','collection_adapter.py','collection_audit.py','collection_watch.py','supervisor.py','windows_job.py','flat_answers.py','category_eligibility.py','perfect_store.py','perfect_store_check.py','perfect_store_admission.py','cold_conversion.py',Path(__file__).name];bundle=engine.code_bundle({n:Path(__file__).with_name(n).read_bytes() for n in names})
 retained={'source_distribution':(nd['raw'],'.json'),'execution_distribution':(nd['execution'],'.json'),'source_distribution_implementation':(nd['originals']['implementation'],'.json'),'source_cold':(cold['raw'],'.json'),'execution_cold':(cold['execution'],'.json'),'source_cold_implementation':(cold['originals']['implementation'],'.json'),'source_ps_result':(ps_raw,'.json'),'source_ps_execution':(metadata_raw,'.json'),'source_ps_implementation':(refs['source_ps_implementation'],'.json'),'admission_manifest':(manifest,'.json'),'implementation':(bundle,'.json'),'scope_configuration':(scope_raw,'.json'),'observed_definition':(engine.canonical({'schema':'mindtec-retained-conversion-definition/1','encoding':'base64','original_sha256':definition_sha256,'content':base64.b64encode(definition).decode()}).encode(),'.json'),**observations,**{k:(raw,'.xlsx' if k.endswith('workbook') else '.json') for k,raw in originals.items()}}
 retained.update({k:(raw,'.json') for k,raw in cold['originals'].items() if k.startswith('cooler_scope_')})
 summary={'unit':'brand_within_family','brand_families':len(result['brand_families']),'monthly_results':len(result['monthly']),'annual_observed_results':len(result['annual_observed_months']),'monthly_states':dict(collections.Counter(s['state'] for s in result['monthly'])),'stores':len(result['stores']),'equipment_visits':len(result['equipment']),'equipment_states':dict(collections.Counter(str(e['value']) for e in result['equipment'])),'findings':len(findings),'verified_original_cells':cell_checks['verified_original_cells'],'ps_checks':checks,'network_delivery':False};rules={'kind':'declared_cold_conversion','version':cold_conversion.VERSION,'reference_sources':{k:engine.sha(v[0]) for k,v in retained.items()}}
 with engine.Engine(target) as e:accepted=e.record_result(engine.canonical(result).encode(),prepared['policy'],rules,findings,summary,retained);head=e.verify()
 return {'run_id':accepted['run_id'],'snapshot_sha256':accepted['snapshot'],'ledger_head':head,'summary':summary}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['distribution-runtime','cold-runtime','runtime','scope','definition-evidence']:p.add_argument('--'+name,required=True,type=Path)
 p.add_argument('--definition-sha256',required=True);a=p.parse_args();print(engine.canonical(execute(a.distribution_runtime,a.cold_runtime,a.runtime,a.scope,a.definition_evidence,a.definition_sha256)))
