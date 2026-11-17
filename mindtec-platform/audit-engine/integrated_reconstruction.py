"""Join compatible reconstruction snapshots, preserving source-index and cell lineage."""
import argparse,copy,collections
from pathlib import Path
import engine,collection_watch,collection_adapter,perfect_store_check

VERSION='integrated-reconstruction/1.0.0'

def identity(r):return (r['kobo_id'],r['month'],r['category'],r['brand_code'],r['brand'])
def summary_key(r):return (r['period'],r['category'],r['brand_code'],r['brand'])

def project(ps,nd,sh,sources):
 if nd.get('source_ps_run_id')!=sources['perfect_store']['run_id'] or sh.get('source_ps_run_id')!=sources['perfect_store']['run_id']:raise ValueError('Reconstructions refer to different PS executions')
 if nd.get('source_ps_snapshot_sha256')!=sources['perfect_store']['snapshot_sha256'] or sh.get('source_ps_snapshot_sha256')!=sources['perfect_store']['snapshot_sha256']:raise ValueError('PS source snapshots differ')
 if len({r['source_sha256'] for r in [ps,nd,sh]})!=1:raise ValueError('Detailed workbook cuts differ')
 def index(rows):
  out={}
  for i,r in enumerate(rows):
   key=identity(r)
   if key in out:raise ValueError('Duplicate source store identity')
   out[key]=(i,r)
  return out
 n=index(nd['stores']);s=index(sh['stores']);p=index(ps['details'])
 if not n or set(n)!=set(s) or not set(p)<=set(n):raise ValueError('Brand/visit cohorts differ')
 cells={};answers={}
 for name in ['cells','answer_evidence']:
  target=cells if name=='cells' else answers
  for dataset in [ps,nd,sh]:
   for key,value in dataset[name].items():
    if engine.sha(engine.canonical(value))!=key:raise ValueError('Source fingerprint differs')
    if key in target and engine.canonical(target[key])!=engine.canonical(value):raise ValueError('Conflicting evidence identifier')
    target[key]=copy.deepcopy(value)
 for a in answers.values():
  if any(cid not in cells for cid in a['cell_ids']):raise ValueError('Original evidence cell absent')
 visits=sorted({(k[0],k[1]) for k in n});vi={k:i for i,k in enumerate(visits)};catalogue=sorted({k[2:] for k in n});ci={k:i for i,k in enumerate(catalogue)};category_codes=sorted({k[0] for k in catalogue});categories={c:i for i,c in enumerate(category_codes)}
 company=collections.defaultdict(set)
 for row in ps['details']:company[(row['category'],row['brand_code'],row['brand'])].add(row['company'])
 if any(len(v)>1 for v in company.values()):raise ValueError('Company mapping differs within one catalogue identity')
 reasons=[];reason_ids={};evidence_sets=[];set_ids={}
 def reason(text):
  if text not in reason_ids:reason_ids[text]=len(reasons);reasons.append(text)
  return reason_ids[text]
 def evidence(ids):
  key=tuple(sorted(set(ids)))
  if any(x not in answers for x in key):raise ValueError('Answer reference missing')
  if key not in set_ids:set_ids[key]=len(evidence_sets);evidence_sets.append(list(key))
  return set_ids[key]
 gates=[];gate_ids={}
 for i,g in enumerate(ps['eligibility_checks']):
  key=(g['kobo_id'],g['month'],g['category'])
  if key in gate_ids:raise ValueError('Duplicate category eligibility')
  gate_ids[key]=len(gates);gates.append({'v':vi[key[:2]],'category':categories[key[2]],'eligible':g['eligible'],'method':g['method'],'reason':reason(g['reason']),'signals':g['signals'],'evidence_set':evidence(g['support']),'source_index':i})
 inventories=[];inventory_ids={}
 for i,inv in enumerate(sh['category_inventories']):
  key=(inv['kobo_id'],inv['month'],inv['category'])
  if key in inventory_ids:raise ValueError('Duplicate shelf inventory')
  inventory_ids[key]=len(inventories);inventories.append({'v':vi[key[:2]],'category':categories[key[2]],'eligible':inv['eligible'],'state':inv['state'],'faces':inv['faces'],'known_faces':inv.get('known_faces_subtotal_not_total'),'rows':inv.get('rows',[]),'other_branches':[{k:v for k,v in b.items() if k!='consumed_columns'} for b in inv.get('other_branches',[])],'unattributed':inv.get('unattributed_auxiliary_observations',[]),'signals':inv['signals'],'evidence_set':evidence(inv['answer_ids']),'source_index':i})
 if set(gate_ids)!=set(inventory_ids):raise ValueError('Eligibility and shelf inventory scopes differ')
 ps_details=[];ps_ids={}
 for key,(i,r) in sorted(p.items()):
  ps_ids[key]=len(ps_details);ps_details.append({'source_index':i,'score':r['score'],'numerator':r['numerator'],'denominator':r['measured_denominator'],'pending':r['pending_components'],'minimum':r['conditional_minimum'],'maximum':r['conditional_maximum'],'components':[{'name':c['component'],'state':c['state'],'value':c['value'],'weight':c['weight'],'reason':reason(c['reason']),'evidence_set':evidence(c['evidence_ids']),'configuration_key':c['configuration_key']} for c in r['components']]})
 stores=[];store_groups=collections.defaultdict(list)
 for key,(ni,nr) in sorted(n.items()):
  si,sr=s[key];gkey=key[:3];g=gates[gate_ids[gkey]];inv=inventories[inventory_ids[gkey]]
  if nr['eligible'] is not g['eligible'] or sr['eligible'] is not g['eligible']:raise ValueError('Source eligibility differs')
  if g['eligible'] is False and key in p or g['eligible'] is not False and key not in p:raise ValueError('PS applicability differs from admitted cohort')
  if sr['category_faces']!=inv['faces']:raise ValueError('Shelf denominator differs from category inventory')
  row={'v':vi[key[:2]],'c':ci[key[2:]],'g':gate_ids[gkey],'i':inventory_ids[gkey],'ps':ps_ids.get(key),'nd':{'source_index':ni,'presence':nr['presence'],'evidence_set':evidence(nr['answer_ids'])},'sh':{'source_index':si,'brand_faces':sr['brand_faces'],'known_brand_faces':sr['known_brand_faces_not_full_share']}}
  index_id=len(stores);stores.append(row);store_groups[(key[1],ci[key[2:]])].append(index_id);store_groups[(key[1][:4],ci[key[2:]])].append(index_id)
 series=[]
 for name,kind in [('monthly','month'),('annual_observed_months','year_observed_months')]:
  ps_s={summary_key(r):(i,r) for i,r in enumerate(ps[name])};nd_s={summary_key(r):(i,r) for i,r in enumerate(nd[name])};sh_s={summary_key(r):(i,r) for i,r in enumerate(sh[name])}
  if len(nd_s)!=len(nd[name]) or len(sh_s)!=len(sh[name]) or set(nd_s)!=set(sh_s) or not set(ps_s)<=set(nd_s):raise ValueError('Metric summary scopes differ')
  for key,(ni,nr) in sorted(nd_s.items()):
   si,sr=sh_s[key];cat=ci[key[1:]];pid,pr=ps_s.get(key,(None,None))
   if pr is None and nr['state']!='no_eligible_base':raise ValueError('Applicable PS aggregate missing')
   ps_metric={'source_index':pid,'value':pr['score'] if pr else None,'minimum':pr['minimum'] if pr else None,'maximum':pr['maximum'] if pr else None,'complete_stores':pr['complete_store_scores'] if pr else 0,'store_months':pr['store_month_observations'] if pr else 0,'eligibility_pending':pr['eligibility_pending'] if pr else 0,'months_observed':pr['months_observed'] if pr else nr['months_observed'],'state':'no_eligible_base' if pr is None else 'complete' if pr['score'] is not None else 'pending_eligibility' if pr['minimum'] is None else 'bounded_missing_components'}
   series.append({'period':key[0],'kind':kind,'c':cat,'stores':store_groups[(key[0],cat)],'ps':ps_metric,'nd':{'source_index':ni,**{k:v for k,v in nr.items() if k not in ['period','period_kind','category','brand_code','brand','store_rows']}},'sh':{'source_index':si,**{k:v for k,v in sr.items() if k not in ['period','period_kind','category','brand_code','brand','store_rows']}}})
 return {'schema':'mindtec-integrated-reconstruction/1','version':VERSION,'source_sha256':ps['source_sha256'],'sources':copy.deepcopy(sources),'visits':[{'kobo_id':v,'month':m} for v,m in visits],'categories':category_codes,'catalogue':[{'category':categories[c],'brand_code':b,'brand':label,'company':next(iter(company[(c,b,label)]),None)} for c,b,label in catalogue],'series':series,'stores':stores,'gates':gates,'inventories':inventories,'ps_details':ps_details,'reasons':reasons,'evidence_sets':evidence_sets,'cells':cells,'answer_evidence':answers,'projection_note':'Selected fields with immutable source snapshot and source-array indices. Not a copy of all upstream result fields.','limits':['Operational reconstructions; not the certified official MindTEC kernel.','All three metrics use one observer-accepted PS source; incompatible runs are rejected.','Company mapping is historical configuration, not proof of a distributor relationship.','Year views retain each metric aggregation: PS mean, distribution pooled visits, shelf pooled faces.','No current official-panel comparison, causal explanation or fraud determination is asserted.']}

def captured(runtime,kind,observer=False):
 root=Path(runtime).resolve()
 if not (root/'audit.sqlite').is_file():raise ValueError('Existing source custody required')
 with engine.Engine(root) as e:
  e.db.execute('BEGIN')
  try:
   head=e.verify();run=None
   if observer:
    for row in e.db.execute('SELECT event_json FROM events ORDER BY seq DESC'):
     event=engine.load_json_bytes(row[0].encode())
     if event['action']=='perfect_store.observer.accepted':run=e.db.execute('SELECT * FROM runs WHERE id=?',(event['payload']['run_id'],)).fetchone();break
   else:run=e.db.execute('SELECT * FROM runs WHERE json_extract(rules_json,\'$.kind\')=? ORDER BY at DESC,id DESC LIMIT 1',(kind,)).fetchone()
   if run is None:raise ValueError('Accepted reconstruction missing')
   rules=engine.load_json_bytes(run['rules_json'].encode())
   if rules.get('kind')!=kind:raise ValueError('Unexpected reconstruction kind')
   raw=collection_watch.object_bytes(e,run['snapshot_hash']);result=engine.load_json_bytes(raw);originals={k:collection_watch.object_bytes(e,v) for k,v in rules['reference_sources'].items()}
   return {'meta':{'run_id':run['id'],'snapshot_sha256':run['snapshot_hash'],'ledger_head':head,'rule_version':rules['version']},'raw':raw,'result':result,'findings':engine.load_json_bytes(run['findings_json'].encode()),'policy':engine.load_json_bytes(run['policy_json'].encode()),'originals':originals,'execution':engine.canonical({'run':dict(run),'verified_head':head}).encode()}
  finally:e.db.execute('ROLLBACK')

def execute(ps_runtime,distribution_runtime,shelf_runtime,runtime):
 target=Path(runtime).resolve();inputs=[Path(p).resolve() for p in [ps_runtime,distribution_runtime,shelf_runtime]]
 if any(target.is_relative_to(p) or p.is_relative_to(target) for p in inputs):raise ValueError('Separate projection custody required')
 ps=captured(ps_runtime,'operational_perfect_store',True);nd=captured(distribution_runtime,'declared_numeric_distribution');sh=captured(shelf_runtime,'declared_shelf_share')
 if any(engine.canonical(c['policy'])!=engine.canonical(ps['policy']) for c in [nd,sh]):raise ValueError('Exclusion policies differ')
 sources={k:v['meta'] for k,v in [('perfect_store',ps),('distribution',nd),('shelf',sh)]};sources['perfect_store']['configuration_version']=ps['result']['configuration_version'];result=project(ps['result'],nd['result'],sh['result'],sources);result['policy']=ps['policy'];result['configuration']=engine.load_json_bytes(ps['originals']['operational_configuration'])
 book=collection_adapter.workbook_tables('retained.xlsx',ps['originals']['detailed_workbook']);checks=perfect_store_check.verify_cells(result,book)
 result['findings']=[{'origin':origin,'finding':f} for origin,cut in [('perfect_store',ps),('shelf',sh)] for f in cut['findings']]
 refs={'source_'+name:(cut['raw'],'.json') for name,cut in [('perfect_store',ps),('distribution',nd),('shelf',sh)]};refs.update({'execution_'+name:(cut['execution'],'.json') for name,cut in [('perfect_store',ps),('distribution',nd),('shelf',sh)]});refs.update({'detailed_workbook':(ps['originals']['detailed_workbook'],'.xlsx'),'normalized_workbook':(ps['originals']['normalized_result_workbook'],'.xlsx'),'operational_configuration':(ps['originals']['operational_configuration'],'.json'),'implementation':(engine.code_bundle({n:Path(__file__).with_name(n).read_bytes() for n in ['engine.py','collection_watch.py','collection_adapter.py','collection_audit.py','invoice_adapter.py','perfect_store_check.py',Path(__file__).name]}),'.json')})
 rules={'kind':'integrated_reconstruction','version':VERSION,'reference_sources':{k:engine.sha(v[0]) for k,v in refs.items()}};summary={'visits':len(result['visits']),'catalogue_entries':len(result['catalogue']),'monthly_rows':sum(s['kind']=='month' for s in result['series']),'observed_year_rows':sum(s['kind']!='month' for s in result['series']),'verified_cells':checks['verified_original_cells']}
 with engine.Engine(target) as e:run=e.record_result(engine.canonical(result).encode(),ps['policy'],rules,[],summary,refs);head=e.verify()
 return {'run_id':run['run_id'],'snapshot':run['snapshot'],'ledger_head':head,'summary':summary}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['ps-runtime','distribution-runtime','shelf-runtime','runtime']:p.add_argument('--'+name,required=True,type=Path)
 a=p.parse_args();print(engine.canonical(execute(a.ps_runtime,a.distribution_runtime,a.shelf_runtime,a.runtime)))
