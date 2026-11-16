"""Declared shelf faces: require a complete category denominator before a share."""
import collections,math,re
from pathlib import Path
import engine,other_faces

VERSION='declared-shelf-share/1.1.0'
IMPLEMENTATION_BYTES=Path(__file__).read_bytes()
OTHER={'otro','otras','otras_marcas','other'}

def integer(a):
 v=a.get('value')
 return int(v) if a.get('state')=='observed' and type(v) in (int,float) and math.isfinite(v) and v>=0 and float(v).is_integer() else None

def inventory(flat,record,category,decision,other_rules=None):
 answers=[];signals=[];other_branches=[];consumed=set()
 def keep(a):answers.append(a);return a
 if decision['eligible'] is False:return {'eligible':False,'state':'not_applicable','faces':None,'faces_by_code':{},'signals':[],'answers':[]}
 if decision['eligible'] is None:signals.append('category_eligibility_pending')
 n=keep(flat.suffix(record,'n_'+category));choice=keep(flat.suffix(record,'marcas_'+category));expected=integer(n);selected=choice['value'].split() if choice['state']=='observed' and isinstance(choice['value'],str) else None
 groups=flat.groups(record,'rep_'+category);faces={};rows=[]
 if expected is None:signals.append('brand_enumeration_count_unresolved')
 if selected is None:signals.append('brand_selection_unresolved')
 elif len(set(selected))!=len(selected):signals.append('brand_selection_repeated')
 if expected is not None and (expected!=len(groups) or selected is not None and expected!=len(selected)):signals.append('brand_enumeration_incomplete')
 for name,fields in sorted(groups.items()):
  def field(suffix):return keep(fields.get(suffix,{'route':name+'/'+suffix,'state':'route_not_mapped','value':None,'cells':[]}))
  code=field('marca_act_'+category);label=field('marca_lbl_'+category);count=field('caras_'+category);value=integer(count);c=code['value'] if code['state']=='observed' and isinstance(code['value'],str) and code['value'] else None
  if c is None:signals.append('brand_identity_unresolved')
  elif c in faces:signals.append('duplicate_brand_row')
  origin='direct_primary_face_cell'
  if c in OTHER:
   rule=(other_rules or {}).get('forms',{}).get(record['form'])
   if not rule:signals.append('other_brand_branch_requires_explicit_mapping')
   else:
    branch=other_faces.resolve(flat,record,category,name,fields,rule);answers.extend(branch.pop('answers'));consumed.update(branch['consumed_columns']);signals.extend(branch['signals']);value=branch['faces'];origin=branch['layout'];other_branches.append(dict(parent_group=name,**branch))
  if value is None:signals.append('face_count_unresolved')
  if c is not None:faces[c]=None if c in faces else value
  rows.append({'group':name,'code':c,'label':label.get('value'),'faces':value,'face_source':origin,'raw_parent_faces':integer(count)})
 if selected is not None and set(selected)!=set(faces):signals.append('selected_brands_and_repetitions_disagree')
 # Preserve filled, unmapped nested-other fields. Do not guess their outer row.
 other_token=re.compile(r'(?:num_otra_marca|otra_marca_(?:sku|caras)|rep_otras_marcas)_'+re.escape(category)+r'(?![A-Za-z0-9_])')
 for header in flat.unmapped[record['form']]:
  if other_token.search(header) and record['row']['cells'][flat.columns[header]] not in (None,'') and header not in consumed:
   keep({'route':None,'state':'unmapped_other_brand_column','value':None,'cells':[flat.cell(record,flat.columns[header])]});signals.append('unmapped_other_brand_observation')
 signals=sorted(set(signals));complete=not signals
 return {'eligible':decision['eligible'],'state':'complete' if complete else 'pending','faces':sum(faces.values()) if complete else None,'known_faces_subtotal_not_total':sum(v for v in faces.values() if v is not None),'faces_by_code':faces,'rows':rows,'other_branches':other_branches,'signals':signals,'answers':answers}

def aggregate(rows,period,kind):
 applicable=[r for r in rows if r['eligible'] is not False];pending=[r for r in applicable if r['state']!='complete'];complete=bool(applicable) and not pending
 numerator=sum(r['brand_faces'] for r in applicable) if complete else None;denominator=sum(r['category_faces'] for r in applicable) if complete else None
 return {'period':period,'period_kind':kind,'brand':rows[0]['brand'],'brand_code':rows[0]['brand_code'],'category':rows[0]['category'],'cohort_store_months':len(rows),'applicable_store_months':len(applicable),'pending_store_months':len(pending),'store_months_with_category_signals':sum(bool(r['category_signals']) for r in rows),'numerator':numerator,'denominator':denominator,'value':100*numerator/denominator if denominator else None,'state':'pending_observations' if pending else 'no_eligible_base' if not applicable else 'zero_observed_faces' if not denominator else 'complete','months_observed':sorted({r['month'] for r in rows}),'store_rows':[r['id'] for r in rows]}

def evaluate(flat,catalog,cohort,eligibility_checks,source_answers,source_cells,other_rules=None):
 if other_rules is not None:
  if other_rules.get('schema')!='mindtec-other-face-layouts/1' or other_rules.get('detailed_workbook_sha256')!=flat.source_sha256 or not isinstance(other_rules.get('version'),str) or not isinstance(other_rules.get('forms'),dict):raise ValueError('Source-bound other-face layout configuration required')
 cohort=list(cohort);identities=[(c['category'],c['brand_code'],c['brand']) for c in catalog]
 if not cohort or len(set(cohort))!=len(cohort) or not identities or len(set(identities))!=len(identities):raise ValueError('Unique admitted cohort and full catalogue required')
 code_labels=collections.defaultdict(set)
 for category,code,brand in identities:code_labels[(category,code)].add(brand)
 if any(code not in OTHER and len(labels)>1 for (_,code),labels in code_labels.items()):raise ValueError('Brand code has multiple labels; explicit homologation required')
 decisions={}
 for c in eligibility_checks:
  key=(c['kobo_id'],c['month'],c['category'])
  if key in decisions:raise ValueError('Repeated eligibility decision')
  decisions[key]=c
 expected={(visit,month,cat) for visit,month in cohort for cat,_,_ in identities}
 if set(decisions)!=expected:raise ValueError('Eligibility decisions differ from admitted cohort/catalogue')
 records={(r['id'],r['month']):r for r in flat.records};answers={};cells={};prepared={};rows=[];monthly=collections.defaultdict(list);annual=collections.defaultdict(list)
 def retain(a):
  ids=[]
  for cell in a.get('cells',[]):cid=engine.sha(engine.canonical(cell));cells[cid]=cell;ids.append(cid)
  binding={'route':a.get('route'),'state':a['state'],'value':a.get('value'),'cell_ids':ids}
  if 'binding_rule' in a:binding['binding_rule']=a['binding_rule']
  aid=engine.sha(engine.canonical(binding));answers[aid]=binding;return aid
 for key in sorted(expected):
  visit,month,cat=key
  if (visit,month) not in records:raise ValueError('Admitted detailed visit missing')
  decision=decisions[key];item=inventory(flat,records[(visit,month)],cat,decision,other_rules);support=[]
  for aid in decision['support']:
   if aid not in source_answers:raise ValueError('Eligibility support missing')
   a=source_answers[aid]
   for cid in a['cell_ids']:
    if cid not in source_cells:raise ValueError('Original eligibility cell missing')
    cells[cid]=source_cells[cid]
   answers[aid]=a;support.append(aid)
  item['answer_ids']=sorted(set(support+[retain(a) for a in item.pop('answers')]));prepared[key]=item
 for cat,code,brand in sorted(identities):
  for visit,month in sorted(cohort):
   decision=decisions[(visit,month,cat)];p=prepared[(visit,month,cat)];value=p['faces_by_code'].get(code,0) if p['state']=='complete' else None
   observed_brand=p['faces_by_code'].get(code) if code not in OTHER or p['state']=='complete' else None
   if p['state']=='complete' and code not in p['faces_by_code']:observed_brand=0
   row={'kobo_id':visit,'month':month,'category':cat,'brand_code':code,'brand':brand,'eligible':p['eligible'],'state':p['state'],'brand_faces':value,'known_brand_faces_not_full_share':observed_brand,'category_faces':p['faces'],'known_category_faces_subtotal_not_total':p.get('known_faces_subtotal_not_total'),'signals':p['signals'],'category_signals':decision['signals'],'answer_ids':p['answer_ids']};row['id']=engine.sha(engine.canonical([visit,month,cat,code,brand]));rows.append(row);monthly[(month,cat,code,brand)].append(row);annual[(month[:4],cat,code,brand)].append(row)
 return {'schema':'mindtec-declared-shelf-share/1','version':VERSION,'source_sha256':flat.source_sha256,'unit':'%','formula':'100 * sum of brand shelf faces / sum of category shelf faces in admitted eligible store-months; no averaging of store percentages.','monthly':[aggregate(rs,k[0],'month') for k,rs in sorted(monthly.items())],'annual_observed_months':[aggregate(rs,k[0],'year_observed_months_pooled_faces') for k,rs in sorted(annual.items())],'stores':rows,'category_inventories':[dict(kobo_id=k[0],month=k[1],category=k[2],**p) for k,p in sorted(prepared.items())],'cells':cells,'answer_evidence':answers,'limits':['Other-brand branches require explicit mapping; parent and child face counts are never added speculatively.','Known face subtotals are not category totals and do not produce a full-cohort share.','Zero faces, no eligible base and pending observations are distinct.','Year view pools observed store-month faces, not complete calendar-year market share.','Category source signals remain visible; arithmetic completeness is not human validation or proof of field truth.','No official panel comparison or fraud determination is asserted.']}
