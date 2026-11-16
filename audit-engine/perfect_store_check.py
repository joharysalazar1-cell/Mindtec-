"""Independently check PS arithmetic, evidence fingerprints and original XLSX cells."""
import collections,math,statistics
import engine,collection_audit
from perfect_store import COMPONENTS

def close(a,b):return a is None and b is None or isinstance(a,(int,float)) and isinstance(b,(int,float)) and math.isclose(a,b,rel_tol=1e-12,abs_tol=1e-10)

def verify_model(result):
 if result.get('schema')!='mindtec-operational-perfect-store/2':raise ValueError('Operational PS result contract required')
 for key,cell in result['cells'].items():
  if engine.sha(engine.canonical(cell))!=key:raise ValueError('Cell fingerprint differs')
 for key,a in result['answer_evidence'].items():
  if engine.sha(engine.canonical(a))!=key or any(cid not in result['cells'] for cid in a['cell_ids']):raise ValueError('Answer evidence binding differs')
 monthly=collections.defaultdict(list);annual=collections.defaultdict(list);seen_stores=set()
 for row in result['details']:
  cs=row['components']
  if len(cs)!=5 or {c['component'] for c in cs}!=set(COMPONENTS):raise ValueError('Five declared components required')
  identity=(row['month'],row['category'],row['brand_code'],row['brand'],row['kobo_id'])
  if identity in seen_stores or row['eligible'] not in (True,None) or row['year']!=row['month'][:4]:raise ValueError('Store-month identity or eligibility differs')
  seen_stores.add(identity)
  for c in cs:
   if c['weight']!=1 or c['state'] not in ('measured','pending','not_applicable'):raise ValueError('Component contract differs')
   if c['state']=='measured':
    if type(c['value']) is not int or c['value'] not in (0,1):raise ValueError('Measured binary component required')
   elif c['value'] is not None:raise ValueError('Unresolved component cannot have a value')
   if any(aid not in result['answer_evidence'] for aid in c['evidence_ids']):raise ValueError('Component evidence missing')
  measured=[c for c in cs if c['state']=='measured'];n=sum(c['value'] for c in measured);den=len(measured);pending=sum(c['state']=='pending' for c in cs)
  expected=100*n/den if den and pending==0 and row['eligible'] is True else None
  if (n,den,pending)!=(row['numerator'],row['measured_denominator'],row['pending_components']) or not close(expected,row['score']):raise ValueError('Store score arithmetic differs')
  lo=100*n/(den+pending) if den+pending else None;hi=100*(n+pending)/(den+pending) if den+pending else None
  if not close(lo,row['conditional_minimum']) or not close(hi,row['conditional_maximum']):raise ValueError('Store uncertainty bounds differ')
  if row['eligibility_evidence'] not in result['answer_evidence']:raise ValueError('Eligibility evidence missing')
  monthly[(row['month'],row['category'],row['brand_code'],row['brand'])].append(row);annual[(row['year'],row['category'],row['brand_code'],row['brand'])].append(row)
 for summaries,groups in [(result['monthly'],monthly),(result['annual_observed_months'],annual)]:
  if len(summaries)!=len(groups):raise ValueError('Summary coverage differs')
  seen=set()
  for s in summaries:
   key=(s['period'],s['category'],s['brand_code'],s['brand']);rows=groups.get(key)
   if not rows or key in seen:raise ValueError('Summary identity differs')
   seen.add(key);vals=[r['score'] for r in rows if r['score'] is not None];unknown=sum(r['eligible'] is None for r in rows);score=statistics.mean(vals) if len(vals)==len(rows) and vals and not unknown else None
   if not close(score,s['score']) or s['store_month_observations']!=len(rows) or s['complete_store_scores']!=len(vals) or s['eligibility_pending']!=unknown:raise ValueError('Summary arithmetic differs')
   if not close(statistics.mean(vals) if vals else None,s['partial_mean_not_population_score']):raise ValueError('Partial mean differs')
   for name,field in [('minimum','conditional_minimum'),('maximum','conditional_maximum')]:
    if not close(None if unknown else statistics.mean(r[field] for r in rows),s[name]):raise ValueError('Summary uncertainty bounds differ')
   if s['months_observed']!=sorted({r['month'] for r in rows}):raise ValueError('Observed month coverage differs')
   if s['unique_visits']!=len({r['kobo_id'] for r in rows}):raise ValueError('Unique visit coverage differs')
   for name in COMPONENTS:
    cs=[c for r in rows for c in r['components'] if c['component']==name];counts={'fulfilled':sum(c['state']=='measured' and c['value']==1 for c in cs),'measured':sum(c['state']=='measured' for c in cs),'pending':sum(c['state']=='pending' for c in cs),'not_applicable':sum(c['state']=='not_applicable' for c in cs)}
    if s['components'][name]!=counts:raise ValueError('Summary component coverage differs')
 return {'store_rows':len(result['details']),'monthly_rows':len(result['monthly']),'cells':len(result['cells']),'answer_bindings':len(result['answer_evidence'])}

def verify_cells(result,workbook):
 if result['source_sha256']!=workbook['provenance']['original_sha256']:raise ValueError('Detailed workbook hash differs')
 tables={t['sheet']:t for t in workbook['tables']};rows={name:{r['source_row']:r for r in t['rows']} for name,t in tables.items()}
 for cell in result['cells'].values():
  t=tables.get(cell['sheet']);row=rows.get(cell['sheet'],{}).get(cell['source_row'])
  if not t or not row or cell['column'] not in t['headers']:raise ValueError('Original cell location absent')
  i=t['headers'].index(cell['column']);letters=''.join(c for c in t['header_coordinates'][i] if c.isalpha());coord=row['coordinates'][i] or letters+str(row['source_row'])
  eid=collection_audit.identifier(row['cells'][t['headers'].index('Envio Kobo')])
  if cell['coordinate']!=coord or cell['kobo_id']!=eid or engine.canonical(cell['value'])!=engine.canonical(row['cells'][i]):raise ValueError('Cell value differs from original workbook')
 return {'verified_original_cells':len(result['cells']),'original_sha256':result['source_sha256']}
