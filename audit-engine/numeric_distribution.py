"""Declared-brand distribution from verified PS presence, with exhaustive scope."""
import collections
from pathlib import Path
import engine,perfect_store_check

VERSION='declared-numeric-distribution/1.0.0'
IMPLEMENTATION_BYTES=Path(__file__).read_bytes()

def aggregate(rows,period,kind):
 present=sum(r['eligible'] is True and r['presence']==1 for r in rows)
 eligible=sum(r['eligible'] is True for r in rows)
 absent=sum(r['eligible'] is True and r['presence']==0 for r in rows)
 pending=eligible-present-absent;eligibility_pending=sum(r['eligible'] is None for r in rows);maximum_denominator=eligible+eligibility_pending
 complete=eligible>0 and not pending and not eligibility_pending
 return {'period':period,'period_kind':kind,'brand':rows[0]['brand'],'brand_code':rows[0]['brand_code'],'category':rows[0]['category'],'cohort_store_months':len(rows),'eligible_confirmed':eligible,'ineligible_confirmed':sum(r['eligible'] is False for r in rows),'eligibility_pending':eligibility_pending,'presence_confirmed':present,'absence_confirmed':absent,'presence_pending_in_eligible':pending,'numerator':present if complete else None,'denominator':eligible if complete else None,'value':100*present/eligible if complete else None,'minimum':100*present/maximum_denominator if maximum_denominator else None,'maximum':100*(present+pending+eligibility_pending)/maximum_denominator if maximum_denominator else None,'state':'complete' if complete else 'pending_observations' if maximum_denominator else 'no_eligible_base','months_observed':sorted({r['month'] for r in rows}),'store_rows':[r['id'] for r in rows]}

def evaluate(ps,catalog,cohort):
 """Cohort contains already policy-eligible visit/month pairs; absence is explicit."""
 perfect_store_check.verify_model(ps)
 identities=[(c['category'],c['brand_code'],c['brand']) for c in catalog]
 if not identities or len(set(identities))!=len(identities):raise ValueError('Unique full brand/category catalogue identities required')
 cohort=list(cohort)
 if not cohort or len(set(cohort))!=len(cohort):raise ValueError('Unique nonempty admitted visit/month cohort required')
 checks={}
 for i,c in enumerate(ps.get('eligibility_checks',[])):
  key=(c['kobo_id'],c['month'],c['category'])
  if key in checks:raise ValueError('Repeated category eligibility decision')
  checks[key]=(i,c)
 details={}
 for i,r in enumerate(ps['details']):
  key=(r['kobo_id'],r['month'],r['category'],r['brand_code'],r['brand'])
  if key in details:raise ValueError('Repeated brand/visit decision')
  details[key]=(i,r)
 expected_checks={(visit,month,category) for visit,month in cohort for category,_,_ in identities}
 if set(checks)!=expected_checks:raise ValueError('Category decisions differ from admitted cohort/catalogue')
 used_details=set();rows=[];monthly=collections.defaultdict(list);annual=collections.defaultdict(list)
 for category,code,brand in sorted(identities):
  for visit,month in sorted(cohort):
   check_index,c=checks[(visit,month,category)];key=(visit,month,category,code,brand);match=details.get(key);support=set(c['support']);presence=None;detail_index=None
   if c['eligible'] is False:
    if match:raise ValueError('Ineligible category unexpectedly has a brand score')
   else:
    if not match:raise ValueError('Missing brand decision cannot silently remove a denominator')
    detail_index,r=match;used_details.add(key)
    if r['eligible'] is not c['eligible']:raise ValueError('Brand and category eligibility disagree')
    components=[x for x in r['components'] if x['component']=='Presencia']
    if len(components)!=1:raise ValueError('Exactly one presence component required')
    p=components[0];support.update(p['evidence_ids'])
    if c['eligible'] is True and p['state']=='measured':
     if type(p['value']) is not int or p['value'] not in (0,1):raise ValueError('Explicit binary presence required')
     presence=p['value']
   if not support or any(k not in ps['answer_evidence'] for k in support):raise ValueError('Original presence/eligibility answer evidence required')
   row={'kobo_id':visit,'month':month,'category':category,'brand_code':code,'brand':brand,'eligible':c['eligible'],'presence':presence,'ps_detail_index':detail_index,'eligibility_check_index':check_index,'answer_ids':sorted(support)}
   row['id']=engine.sha(engine.canonical([visit,month,category,code,brand]));rows.append(row);monthly[(month,category,code,brand)].append(row);annual[(month[:4],category,code,brand)].append(row)
 if used_details!=set(details):raise ValueError('Unexpected brand decisions outside admitted cohort/catalogue')
 used_answers={k for row in rows for k in row['answer_ids']};answers={k:ps['answer_evidence'][k] for k in sorted(used_answers)};cells={cid:ps['cells'][cid] for a in answers.values() for cid in a['cell_ids']}
 return {'schema':'mindtec-declared-numeric-distribution/1','version':VERSION,'source_sha256':ps['source_sha256'],'source_ps_rule_version':ps['version'],'unit':'%','formula':'100 * confirmed brand-presence stores / confirmed category-eligible stores; exact result only when presence and eligibility are resolved.','monthly':[aggregate(rs,key[0],'month') for key,rs in sorted(monthly.items())],'annual_observed_months':[aggregate(rs,key[0],'year_observed_months_pooled_ratio') for key,rs in sorted(annual.items())],'stores':rows,'answer_evidence':answers,'cells':cells,'limits':['Derived from declared presence in the retained operational PS reconstruction; not independent evidence of field truth.','Pending answers never become confirmed absence; unresolved eligibility remains explicit.','Minimum and maximum are arithmetic missing-data bounds conditional on a nonzero eligible base, not confidence intervals.','Year values pool observed store-month numerators and denominators; not a mean of monthly percentages or a complete calendar year.','No agreement with the official panel is asserted without compatible source, scope and rule versions.']}
