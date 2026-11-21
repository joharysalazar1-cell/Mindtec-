"""Attach company declarations once, without manufacturing brand-specific samples."""
import copy
import engine

def attach(base, source, metadata):
 r=copy.deepcopy(base);ps=r['sources']['perfect_store']
 if source.get('source_ps_run_id')!=ps['run_id'] or source.get('source_ps_snapshot_sha256')!=ps['snapshot_sha256'] or source.get('source_sha256')!=r['source_sha256']:raise ValueError('Company availability source differs')
 for name in ['cells','answer_evidence']:
  for key,value in source[name].items():
   if engine.sha(engine.canonical(value))!=key or key in r[name] and engine.canonical(r[name][key])!=engine.canonical(value):raise ValueError('Company evidence fingerprint differs')
   r[name][key]=copy.deepcopy(value)
 for answer in r['answer_evidence'].values():
  if any(cid not in r['cells'] for cid in answer['cell_ids']):raise ValueError('Company evidence cell missing')
 sets={tuple(ids):i for i,ids in enumerate(r['evidence_sets'])}
 def evidence(ids):
  key=tuple(sorted(set(ids)))
  if any(a not in r['answer_evidence'] for a in key):raise ValueError('Company answer missing')
  if key not in sets:sets[key]=len(r['evidence_sets']);r['evidence_sets'].append(list(key))
  return sets[key]
 visits={(v['kobo_id'],v['month']):i for i,v in enumerate(r['visits'])};companies=source['companies']
 if not companies or len(set(companies))!=len(companies):raise ValueError('Unique company universe required')
 company_ids={co:i for i,co in enumerate(companies)};rows=[];keys={};ids={}
 for index,row in enumerate(source['stores']):
  key=(row['kobo_id'],row['month'],row['company']);visit=key[:2]
  if key in keys or row['id'] in ids or visit not in visits or row['company'] not in company_ids:raise ValueError('Company store scope differs')
  if row['state']=='complete' and (row['eligible'] is not True or type(row['no_declared_stockout']) is not int or row['no_declared_stockout'] not in (0,1)):raise ValueError('Invalid complete company declaration')
  if row['eligible'] is False and (row['state']!='not_applicable' or row['questionnaire_covers_company'] is not True):raise ValueError('Non-buyer requires offered company')
  keys[key]=len(rows);ids[row['id']]=len(rows);rows.append({'source_index':index,'v':visits[visit],'company':company_ids[row['company']],**{k:copy.deepcopy(row[k]) for k in ['eligible','questionnaire_covers_company','state','no_declared_stockout','signals']},'evidence_set':evidence(row['answer_ids'])})
 if set(keys)!={(v,m,c) for v,m in visits for c in companies}:raise ValueError('Company declarations must retain every admitted visit')
 inventories=[];inventory_keys=set()
 for index,inv in enumerate(source['inventories']):
  key=(inv['kobo_id'],inv['month'])
  if key not in visits or key in inventory_keys:raise ValueError('Company inventory scope differs')
  inventory_keys.add(key);inventories.append({'source_index':index,'v':visits[key],**{k:copy.deepcopy(inv[k]) for k in ['expected_companies','selected_companies','scope_signals']},'evidence_set':evidence(inv['answer_ids']),'stock_rows':[{**{k:copy.deepcopy(v) for k,v in item.items() if k!='answer_ids'},'evidence_set':evidence(item['answer_ids'])} for item in inv['stock_rows']]})
 if inventory_keys!=set(visits):raise ValueError('Company inventory visit missing')
 series=[]
 for name,kind in [('monthly','month'),('annual_observed_months','year_observed_months')]:
  seen=set();periods={m if kind=='month' else m[:4] for _,m in visits}
  for index,item in enumerate(source[name]):
   key=(item['period'],item['company'])
   if key in seen or key[0] not in periods or key[1] not in company_ids:raise ValueError('Company aggregate scope differs')
   seen.add(key);expected=[(v,m,c) for v,m,c in keys if c==key[1] and (m if kind=='month' else m[:4])==key[0]];indices=sorted(keys[k] for k in expected)
   try:actual=[ids[sid] for sid in item['store_rows']]
   except KeyError as exc:raise ValueError('Company aggregate references unknown store') from exc
   if len(actual)!=len(set(actual)) or set(actual)!=set(indices):raise ValueError('Company aggregate omitted or duplicated visits')
   group=[rows[i] for i in indices];applicable=[s for s in group if s['eligible'] is not False];pending=[s for s in applicable if s['state']!='complete'];complete=bool(applicable) and not pending
   denominator=len(applicable) if complete else None;numerator=sum(s['no_declared_stockout'] for s in applicable) if complete else None
   checks={'cohort_store_months':len(group),'applicable_store_months':len(applicable),'pending_store_months':len(pending),'not_covered_store_months':sum(s['state']=='not_covered_by_questionnaire' for s in group),'numerator':numerator,'denominator':denominator,'value':100*numerator/denominator if denominator else None,'stockout_numerator':denominator-numerator if denominator is not None else None,'state':'not_covered_by_questionnaire' if all(s['state']=='not_covered_by_questionnaire' for s in group) else 'pending_observations' if pending else 'no_declared_buyers' if not applicable else 'complete','months_observed':sorted({r['visits'][s['v']]['month'] for s in group})}
   if any(item.get(k)!=v for k,v in checks.items()):raise ValueError('Company aggregate does not match all store declarations')
   series.append({'source_index':index,'period':key[0],'kind':kind,'company':company_ids[key[1]],'stores':indices,**copy.deepcopy(checks)})
  if seen!={(p,co) for p in periods for co in companies}:raise ValueError('Company summary missing')
 references={}
 for ref in source['brand_references']:
  key=(ref['category'],ref['brand_code'],ref['brand'])
  if key in references:raise ValueError('Duplicate company brand reference')
  references[key]=ref
 expected_catalog={(r['categories'][c['category']],c['brand_code'],c['brand']) for c in r['catalogue']}
 if set(references)!=expected_catalog:raise ValueError('Company reference catalogue differs')
 brand_references=[]
 for index,c in enumerate(r['catalogue']):
  ref=references[(r['categories'][c['category']],c['brand_code'],c['brand'])];co=ref['company'];expected=c['company'] if c['company'] in company_ids else None
  if co!=expected:raise ValueError('Historical company mapping differs')
  brand_references.append({'catalogue_index':index,'company':company_ids[co] if co is not None else None,'mapping_state':ref['mapping_state']})
 r['availability']={'companies':copy.deepcopy(companies),'stores':rows,'inventories':inventories,'series':series,'brand_references':brand_references,'question_universe':copy.deepcopy(source['question_universe']),'formula':source['formula'],'definition_evidence_sha256':source.get('definition_evidence_sha256'),'mapping_version':source['mapping_version'],'limits':copy.deepcopy(source['limits'])};r['sources']['availability']=copy.deepcopy(metadata)
 r['limits'].append('Company availability is attached once per company/period, not as independent brand results. Category filters select references, never narrow company buyer denominators.')
 return r
