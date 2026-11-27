"""Attach POP without changing source metrics, presence denominators, or absence policy."""
import copy
import engine

def attach(base,pop,metadata):
 r=copy.deepcopy(base);ps=r['sources']['perfect_store']
 if pop.get('source_ps_run_id')!=ps['run_id'] or pop.get('source_ps_snapshot_sha256')!=ps['snapshot_sha256'] or pop.get('source_sha256')!=r['source_sha256'] or pop.get('configuration_version')!=r['configuration']['version']:raise ValueError('POP reconstruction source differs')
 q=pop['question_universe']
 if q.get('detailed_workbook_sha256')!=r['source_sha256'] or q.get('version')!=pop['question_universe_version'] or pop['absence_policy']!=q.get('unselected_owner_policy','strict_offered_owner_coverage'):raise ValueError('POP questionnaire or absence policy differs')
 for name in ['cells','answer_evidence']:
  for key,value in pop[name].items():
   if engine.sha(engine.canonical(value))!=key or key in r[name] and engine.canonical(r[name][key])!=engine.canonical(value):raise ValueError('POP evidence fingerprint differs')
   r[name][key]=copy.deepcopy(value)
 for answer in r['answer_evidence'].values():
  if any(cid not in r['cells'] for cid in answer['cell_ids']):raise ValueError('POP original cell missing')
 sets={tuple(ids):i for i,ids in enumerate(r['evidence_sets'])}
 def evidence(ids):
  key=tuple(sorted(set(ids)))
  if any(a not in r['answer_evidence'] for a in key):raise ValueError('POP answer missing')
  if key not in sets:sets[key]=len(r['evidence_sets']);r['evidence_sets'].append(list(key))
  return sets[key]
 visits={(v['kobo_id'],v['month']):i for i,v in enumerate(r['visits'])};invs=[];seen=set()
 for index,inv in enumerate(pop['inventories']):
  key=(inv['kobo_id'],inv['month'])
  if key not in visits or key in seen or inv['form'] not in q['forms']:raise ValueError('POP inventory cohort or form differs')
  seen.add(key);invs.append({'source_index':index,'v':visits[key],**copy.deepcopy({k:inv[k] for k in ['form','gate','selected_categories','positive_companies','scope_signals','negative_uncertainty']}),'evidence_set':evidence(inv['answer_ids']),'families':[{**copy.deepcopy({k:v for k,v in f.items() if k!='answer_id'}),'evidence_set':evidence([f['answer_id']])} for f in inv['families']]})
 if seen!=set(visits):raise ValueError('POP visit inventory omitted')
 companies=[];companykeys=set();companyids=set();companyset=set()
 for index,cr in enumerate(pop['company_rows']):
  key=(cr['kobo_id'],cr['month'],cr['company']);i=cr['inventory_index']
  if key in companykeys or cr['id'] in companyids or not isinstance(i,int) or i<0 or i>=len(invs) or invs[i]['v']!=visits.get(key[:2]):raise ValueError('POP company identity or inventory differs')
  if cr['value'] is not None and (type(cr['value']) is not int or cr['value'] not in (0,1)) or cr['state']!=('complete' if cr['value'] is not None else 'pending'):raise ValueError('POP company declaration invalid')
  companykeys.add(key);companyids.add(cr['id']);companyset.add(cr['company']);companies.append({'source_index':index,'v':invs[i]['v'],**copy.deepcopy({k:cr[k] for k in ['company','value','state','reason','signals','inventory_index']}),'evidence_set':evidence(cr['answer_ids'])})
 if companykeys!={(v,m,c) for v,m in visits for c in companyset} or not companyset:raise ValueError('POP company declarations omitted')
 rows={};ids={}
 for index,row in enumerate(pop['stores']):
  key=tuple(row[k] for k in ['kobo_id','month','category','brand_code','brand'])
  if key in rows or row['id'] in ids:raise ValueError('Duplicate POP brand/visit identity')
  rows[key]=(index,row);ids[row['id']]=key
 used=set();source_to_store={}
 for index,store in enumerate(r['stores']):
  v=r['visits'][store['v']];c=r['catalogue'][store['c']];key=(v['kobo_id'],v['month'],r['categories'][c['category']],c['brand_code'],c['brand'])
  if key not in rows:raise ValueError('POP brand visit missing')
  source_index,row=rows[key];used.add(key);source_to_store[row['id']]=index;gate=r['gates'][store['g']]
  if row['eligible'] is not gate['eligible'] or row['presence']!=store['nd']['presence']:raise ValueError('POP presence denominator differs from distribution')
  co=c['company'] if c['company'] in companyset else None
  if row['company']!=co or row['presence_source_id']!=engine.sha(engine.canonical(list(key))):raise ValueError('POP historical company or presence source differs')
  cr=companies[row['company_row_index']] if row['company_row_index'] is not None and 0<=row['company_row_index']<len(companies) else None
  if cr is not None and (cr['v']!=store['v'] or cr['company']!=co) or co is not None and cr is None:raise ValueError('POP shared company declaration differs')
  inbase=gate['eligible'] is True and row['presence']==1;pending=gate['eligible'] is None or gate['eligible'] is True and row['presence'] is None
  expected=cr['value'] if inbase and cr is not None else None;state='not_in_brand_presence_base' if not inbase and not pending else 'complete' if expected is not None else 'pending'
  if row['pop']!=expected or row['state']!=state:raise ValueError('POP brand result contradicts company or applicability')
  support=set(r['evidence_sets'][store['nd']['evidence_set']])|(set(r['evidence_sets'][cr['evidence_set']]) if cr else set())
  if set(row['answer_ids'])!=support:raise ValueError('POP presence and material support differ')
  store['pp']={'source_index':source_index,'company_row':row['company_row_index'],'value':row['pop'],'state':row['state'],'signals':copy.deepcopy(row['signals']),'evidence_set':evidence(row['answer_ids'])}
 if used!=set(rows):raise ValueError('POP extra visits outside admitted cohort')
 for name,kind in [('monthly','month'),('annual_observed_months','year_observed_months')]:
  summaries={tuple(s[k] for k in ['period','category','brand_code','brand']):(i,s) for i,s in enumerate(pop[name])};series=[s for s in r['series'] if s['kind']==kind]
  if len(summaries)!=len(pop[name]) or len(series)!=len(summaries):raise ValueError('POP summary scope differs')
  for item in series:
   c=r['catalogue'][item['c']];key=(item['period'],r['categories'][c['category']],c['brand_code'],c['brand'])
   if key not in summaries:raise ValueError('POP aggregate missing')
   index,s=summaries[key]
   try:indices=[source_to_store[x] for x in s['store_rows']]
   except KeyError as exc:raise ValueError('POP aggregate store reference unknown') from exc
   if len(indices)!=len(set(indices)) or set(indices)!=set(item['stores']):raise ValueError('POP aggregate dropped or duplicated visits')
   group=[rows[ids[x]][1] for x in s['store_rows']];base_rows=[x for x in group if x['eligible'] is True and x['presence']==1];unknown=sum(x['eligible'] is None or x['eligible'] is True and x['presence'] is None for x in group);missing=sum(x['pop'] is None for x in base_rows);positive=sum(x['pop']==1 for x in base_rows);possible=len(base_rows)+unknown;complete=bool(base_rows) and not unknown and not missing
   checks={'cohort_store_months':len(group),'confirmed_brand_present':len(base_rows),'base_pending_store_months':unknown,'pop_pending_in_present':missing,'known_pop_positive':positive,'known_pop_negative':sum(x['pop']==0 for x in base_rows),'numerator':positive if complete else None,'denominator':len(base_rows) if complete else None,'value':100*positive/len(base_rows) if complete else None,'minimum':100*positive/possible if possible else None,'maximum':100*(positive+missing+unknown)/possible if possible else None,'state':'pending_observations' if unknown or missing else 'complete' if base_rows else 'no_brand_presence_base','months_observed':sorted({x['month'] for x in group})}
   if any(s.get(k)!=v for k,v in checks.items()):raise ValueError('POP summary differs from all source store declarations')
   item['pp']={'source_index':index,**copy.deepcopy(checks)}
 r['pop_inventories']=invs;r['pop_companies']=companies;r['pop_scope']=copy.deepcopy(q);r['pop_definition_evidence_sha256']=pop['definition_evidence_sha256'];r['sources']['pop']=copy.deepcopy(metadata);r['limits'].append('POP uses the versioned absence policy: an answered section without owner-company material may be a real zero. Its denominator is brand presence, not company purchasing or category eligibility.')
 return r
