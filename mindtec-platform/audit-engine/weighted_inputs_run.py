"""Retain DP input readiness separately from any reconstructed indicator result."""
import argparse,base64,collections,re
from pathlib import Path
import engine,cold_conversion_run as capture,perfect_store_admission as admission,perfect_store_check,weighted_inputs


def execute(shelf_runtime,conversion_runtime,runtime,definition_path,definition_sha256,purchase_bindings_path=None):
 target=Path(runtime).resolve();inputs=[Path(p).resolve() for p in [shelf_runtime,conversion_runtime]]
 if any(target.is_relative_to(p) or p.is_relative_to(target) for p in inputs):raise ValueError('Separate weighted-input custody required')
 definition_path=Path(definition_path).resolve()
 if definition_path.is_relative_to(target):raise ValueError('Definition must be outside output custody')
 definition=definition_path.read_bytes()
 if len(definition)>2000000 or not re.fullmatch('[0-9a-f]{64}',definition_sha256) or engine.sha(definition)!=definition_sha256:raise ValueError('Weighted definition evidence differs')
 bindings=None;binding_refs={}
 if purchase_bindings_path is not None:
  path=Path(purchase_bindings_path).resolve()
  if path.is_relative_to(target):raise ValueError('Purchase bindings must be outside output custody')
  raw=path.read_bytes()
  if len(raw)>100000:raise ValueError('Purchase bindings too large')
  bindings=engine.load_json_bytes(raw);binding_refs['purchase_bindings']=(raw,'.json')
  for index,item in enumerate(bindings.get('observations',[])):
   path=Path(item['path'])
   if not path.is_absolute() or path.resolve().is_relative_to(target):raise ValueError('External absolute purchase observation required')
   raw=path.read_bytes()
   if len(raw)>2000000 or engine.sha(raw)!=item.get('sha256'):raise ValueError('Purchase observation hash differs')
   binding_refs['purchase_binding_observation_'+str(index+1)]=(engine.canonical({'form':item['form'],'encoding':'base64','original_sha256':engine.sha(raw),'content':base64.b64encode(raw).decode()}).encode(),'.json')
 shelf=capture.capture(inputs[0],'declared_shelf_share');conversion=capture.capture(inputs[1],'declared_cold_conversion')
 if engine.canonical(shelf['policy'])!=engine.canonical(conversion['policy']):raise ValueError('Weighted-input exclusion policy differs')
 refs=conversion['originals'];originals={k:refs[k] for k in admission.SOURCE_LIMITS};a=admission.contract(refs['admission_manifest'],target,target.parent/'reports');p=admission.prepare(a,originals);ps=engine.load_json_bytes(refs['source_ps_result'])
 if engine.sha(refs['source_ps_result'])!=conversion['result']['source_ps_snapshot_sha256'] or engine.canonical(p['policy'])!=engine.canonical(conversion['policy']):raise ValueError('Weighted-input accepted source differs')
 result=weighted_inputs.evaluate(p['flat'],shelf['result'],conversion['result'],bindings);result.update(source_shelf=shelf['meta'],source_conversion=conversion['meta'],definition_evidence_sha256=definition_sha256,purchase_header_bindings=bindings)
 checks=perfect_store_check.verify_cells(result,p['detailed_book']);policy_visits={(r['id'],r['month']) for r in p['flat'].records if r['id'] not in {str(e['id']) for e in p['policy']['exclusions']}}
 if policy_visits!={(r['kobo_id'],r['month']) for r in result['equipment']}:raise ValueError('Weighted-input policy cohort differs')
 finding={'rule':'weighted_distribution_method_not_exported','rule_version':weighted_inputs.VERSION,'severity':'info','title':'Pesos de distribución ponderada requieren regla compatible','evidence':{'source_sha256':result['source_sha256'],'definition_sha256':definition_sha256,'unresolved':['company_to_category_purchase_allocation','range_and_frequency_mapping','door_applicability_by_category','purchase_and_size_weight_normalization']},'explanation':'Se conservan compras por empresa, rangos, frecuencia y tamaño observado sin inventar una equivalencia. Estos insumos no son un porcentaje DP; no implican fraude ni una decisión humana.','disposition':'methodology_pending'};finding['fingerprint']=engine.sha(engine.canonical(finding))
 names=['purchase_binding.py','weighted_inputs.py','weighted_inputs_run.py','cold_conversion.py','cold_conversion_run.py','perfect_store_admission.py','perfect_store_check.py','perfect_store.py','flat_answers.py','category_eligibility.py','engine.py','collection_watch.py','collection_adapter.py','collection_audit.py','invoice_adapter.py','windows_job.py','supervisor.py']
 retained={'implementation':(engine.code_bundle({n:Path(__file__).with_name(n).read_bytes() for n in names}),'.json'),'source_shelf':(shelf['raw'],'.json'),'source_shelf_execution':(shelf['execution'],'.json'),'source_shelf_implementation':(shelf['originals']['implementation'],'.json'),'source_conversion':(conversion['raw'],'.json'),'source_conversion_execution':(conversion['execution'],'.json'),'source_conversion_implementation':(refs['implementation'],'.json'),'source_ps_result':(refs['source_ps_result'],'.json'),'source_ps_execution':(refs['source_ps_execution'],'.json'),'source_ps_implementation':(refs['source_ps_implementation'],'.json'),'admission_manifest':(refs['admission_manifest'],'.json'),'scope_configuration':(refs['scope_configuration'],'.json'),'observed_definition':(engine.canonical({'encoding':'base64','original_sha256':definition_sha256,'content':base64.b64encode(definition).decode()}).encode(),'.json'),**{k:(v,'.xlsx' if k.endswith('workbook') else '.json') for k,v in originals.items()},**{k:(v,'.json') for k,v in refs.items() if k.startswith('scope_observation_')}}
 retained.update(binding_refs)
 summary={'visits':len(result['equipment']),'category_visits':len(result['category_stores']),'total_cooling_door_states':dict(collections.Counter(r['state'] for r in result['equipment'])),'eligible_category_visits':sum(r['eligible'] is True for r in result['category_stores']),'eligible_complete_size_components':sum(r['eligible'] is True and r['size_components_state']=='complete' for r in result['category_stores']),'verified_original_cells':checks['verified_original_cells'],'official_dp_calculated':False,'network_delivery':False}
 rules={'kind':'weighted_input_readiness','version':weighted_inputs.VERSION,'reference_sources':{k:engine.sha(v[0]) for k,v in retained.items()}}
 with engine.Engine(target) as e:accepted=e.record_result(engine.canonical(result).encode(),p['policy'],rules,[finding],summary,retained);head=e.verify()
 return {'run_id':accepted['run_id'],'snapshot_sha256':accepted['snapshot'],'ledger_head':head,'summary':summary}


if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for n in ['shelf-runtime','conversion-runtime','runtime','definition-evidence']:p.add_argument('--'+n,required=True,type=Path)
 p.add_argument('--definition-sha256',required=True);p.add_argument('--purchase-bindings',type=Path);a=p.parse_args();print(engine.canonical(execute(a.shelf_runtime,a.conversion_runtime,a.runtime,a.definition_evidence,a.definition_sha256,a.purchase_bindings)))
