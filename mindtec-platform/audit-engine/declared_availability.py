"""Company stockout declarations among declared buyers, not SKU availability."""
import collections, math, re
from pathlib import Path
import engine, perfect_store

VERSION='declared-company-availability/1.1.1'
IMPLEMENTATION_BYTES=Path(__file__).read_bytes()
UNVERIFIED={'sincorrespondenciaverificada'}

def ps_scope_findings(ps,result):
 """Flag an unsupported historical PS denominator, without guessing a new score."""
 if ps['source_sha256']!=result['source_sha256']:raise ValueError('PS scope comparison requires one workbook')
 rows={(r['kobo_id'],r['month'],r['company']):r for r in result['stores']};groups={}
 for index,detail in enumerate(ps['details']):
  co=detail['company'];row=rows.get((detail['kobo_id'],detail['month'],co));components=[c for c in detail['components'] if c['component']=='Sin quiebre']
  if row is None or row['questionnaire_covers_company'] is not False or len(components)!=1 or components[0]['state']!='not_applicable':continue
  key=(detail['month'],co);item=groups.setdefault(key,{'month':key[0],'company':co,'detail_indices':[],'kobo_ids':set(),'answer_ids':set(),'previous_complete_scores':0})
  item['detail_indices'].append(index);item['kobo_ids'].add(detail['kobo_id']);item['answer_ids'].update(row['answer_ids']);item['previous_complete_scores']+=detail['score'] is not None
 findings=[]
 for _,item in sorted(groups.items()):
  evidence={'source_sha256':result['source_sha256'],'source_ps_run_id':result['source_ps_run_id'],'source_ps_snapshot_sha256':result['source_ps_snapshot_sha256'],'question_universe_version':result['question_universe_version'],**{k:sorted(v) if isinstance(v,set) else v for k,v in item.items()}}
  f={'rule':'ps_stock_inapplicability_not_supported_by_question_universe','rule_version':VERSION,'severity':'medium','title':'Aplicabilidad histórica de Sin quiebre en Perfect Store por revisar','evidence':evidence,'explanation':'El componente histórico quedó No aplica para una empresa que no figuraba entre las opciones de compra de ese formulario. Esa ausencia no prueba que la tienda no comprara a la empresa. Se requiere revisar y reconstruir el componente y sus denominadores; no se imputa un puntaje corregido ni se decide fraude.','disposition':'methodological_review_required'};f['fingerprint']=engine.sha(engine.canonical({'rule':f['rule'],'version':VERSION,'evidence':evidence}));findings.append(f)
 return findings

def integer(answer):
 v=answer.get('value')
 return int(v) if answer.get('state')=='observed' and type(v) in (int,float) and math.isfinite(v) and v>=0 and float(v).is_integer() else None

def aggregate(rows,period,kind):
 applicable=[r for r in rows if r['eligible'] is not False];pending=[r for r in applicable if r['state']!='complete'];complete=bool(applicable) and not pending
 denominator=len(applicable) if complete else None;numerator=sum(r['no_declared_stockout'] for r in applicable) if complete else None
 return {'period':period,'period_kind':kind,'company':rows[0]['company'],'cohort_store_months':len(rows),'applicable_store_months':len(applicable),'pending_store_months':len(pending),'not_covered_store_months':sum(r['state']=='not_covered_by_questionnaire' for r in rows),'numerator':numerator,'denominator':denominator,'value':100*numerator/denominator if denominator else None,'stockout_numerator':denominator-numerator if denominator is not None else None,'state':'not_covered_by_questionnaire' if all(r['state']=='not_covered_by_questionnaire' for r in rows) else 'pending_observations' if pending else 'no_declared_buyers' if not applicable else 'complete','months_observed':sorted({r['month'] for r in rows}),'store_rows':[r['id'] for r in rows]}

def evaluate(flat,catalog,cohort,configuration,questionnaire_scope=None):
 if configuration.get('schema')!='mindtec-operational-perfect-store-config/1' or not isinstance(configuration.get('version'),str):raise ValueError('Versioned historical owner mapping required')
 aliases=configuration['company_aliases'];owners=configuration['company_by_brand'];companies=sorted((set(aliases.values())|set(owners.values()))-UNVERIFIED)
 if not companies or any(not isinstance(k,str) or not isinstance(v,str) or not k or not v for k,v in aliases.items()):raise ValueError('Explicit company aliases required')
 def company(value):return aliases.get(perfect_store.norm(value)) if isinstance(value,str) else None
 cohort=list(cohort);identities=[(c['category'],c['brand_code'],c['brand']) for c in catalog]
 if not cohort or len(set(cohort))!=len(cohort) or not identities or len(set(identities))!=len(identities):raise ValueError('Unique admitted cohort and catalogue required')
 records={(r['id'],r['month']):r for r in flat.records}
 if any(key not in records for key in cohort):raise ValueError('Admitted detailed visit absent')
 offered={}
 if questionnaire_scope is not None:
  q=questionnaire_scope
  if q.get('schema')!='mindtec-company-question-universe/1' or q.get('detailed_workbook_sha256')!=flat.source_sha256 or not isinstance(q.get('version'),str) or not q['version'].strip() or not isinstance(q.get('forms'),dict):raise ValueError('Source-bound company question universe required')
  if set(q['forms'])!={records[key]['form'] for key in cohort}:raise ValueError('Question universe must cover exactly the admitted forms')
  for form,item in q['forms'].items():
   choices=item.get('offered_companies') if isinstance(item,dict) else None
   if not isinstance(choices,list) or not choices or len(set(choices))!=len(choices) or any(co not in companies for co in choices):raise ValueError('Explicit unique homologated company choices required')
   offered[form]=set(choices)
 cells={};answers={};inventories=[];stores=[];monthly=collections.defaultdict(list);annual=collections.defaultdict(list)
 def retain(a):
  ids=[]
  for cell in a.get('cells',[]):
   key=engine.sha(engine.canonical(cell));cells[key]=cell;ids.append(key)
  binding={'route':a.get('route'),'state':a['state'],'value':a.get('value'),'cell_ids':ids};key=engine.sha(engine.canonical(binding));answers[key]=binding;return key
 def missing(route):return {'route':route,'state':'route_not_mapped','value':None,'cells':[]}
 for visit,month in sorted(cohort):
  r=records[(visit,month)];selection=flat.suffix(r,'empresas_compra');counter=flat.suffix(r,'n_empresas_compra');expected=integer(counter);groups=flat.groups(r,'rep_stock_empresa');scope_sources=[selection,counter];signals=[];selected=None
  if selection['state']=='observed' and isinstance(selection['value'],str):selected=selection['value'].split()
  elif expected==0 and selection['state']=='empty_observation' and not groups:selected=[]
  normalized=[company(x) for x in selected] if selected is not None else None
  allowed=offered.get(r['form'])
  if normalized is None:signals.append('purchase_selection_unresolved')
  elif any(c not in companies for c in normalized):signals.append('purchase_company_not_homologated')
  elif len(normalized)!=len(set(normalized)):signals.append('duplicate_purchase_company')
  if allowed is not None and normalized is not None and any(co not in allowed for co in normalized):signals.append('selected_company_outside_admitted_question_choices')
  if expected is None:signals.append('purchase_count_unresolved')
  elif selected is not None and expected!=len(selected):signals.append('purchase_count_and_selection_disagree')
  stock={};indices=[];details=[]
  for name,fields in sorted(groups.items()):
   match=re.fullmatch(r'rep_stock_empresa\[([1-9]\d*)\]',name);indices.append(int(match[1]) if match else None)
   identity=fields.get('empresa_actual_stock',missing(name+'/empresa_actual_stock'));scope_sources.append(identity);co=company(identity.get('value')) if identity['state']=='observed' else None
   sources=list(fields.values());binary=fields.get('hay_quiebre_empresa',missing(name+'/hay_quiebre_empresa'));sources.append(binary);value=binary['value'] if binary['state']=='observed' and binary['value'] in ('si','no') else None;row_signals=[]
   if co not in companies:signals.append('stock_company_not_homologated')
   elif co in stock:signals.append('duplicate_stock_company')
   detail_fields=[fields.get(k,missing(name+'/'+k)) for k in ['marca_quiebre','motivo_quiebre','tiempo_agotado']];sources.extend(detail_fields)
   if value is None:row_signals.append('stockout_declaration_unresolved')
   if value=='no' and any(cell['value'] not in (None,'') for a in detail_fields for cell in a['cells']):row_signals.append('negative_stockout_with_positive_details');value=None
   item={'group':name,'company':co,'declaration':value,'no_declared_stockout':1 if value=='no' else 0 if value=='si' else None,'signals':row_signals,'answer_ids':sorted({retain(a) for a in sources})};details.append(item)
   if co is not None:stock[co]=item
  if expected is not None and (expected!=len(groups) or set(indices)!=set(range(1,expected+1))):signals.append('stock_enumeration_incomplete')
  if normalized is not None and set(normalized)!=set(stock):signals.append('purchase_and_stock_companies_disagree')
  signals=sorted(set(signals));support=sorted({retain(a) for a in scope_sources});inventories.append({'kobo_id':visit,'month':month,'expected_companies':expected,'selected_companies':normalized,'scope_signals':signals,'answer_ids':support,'stock_rows':details})
  # All uncertain identity/enumeration scopes stay pending, including companies
  # omitted from an incomplete selector. No denominator is made artificially small.
  for co in companies:
   not_covered=not signals and allowed is not None and co not in allowed
   unknown_universe=not signals and allowed is None and co not in normalized
   eligible=None if signals or not_covered or unknown_universe else co in normalized;item=stock.get(co);value=item['no_declared_stockout'] if item and eligible is True else None;row_signals=signals+(item['signals'] if item else [])+(['company_not_offered_in_questionnaire'] if not_covered else ['company_question_universe_unverified'] if unknown_universe else [])
   row={'id':engine.sha(engine.canonical([visit,month,co])),'kobo_id':visit,'month':month,'company':co,'eligible':eligible,'questionnaire_covers_company':None if allowed is None else co in allowed,'state':'not_covered_by_questionnaire' if not_covered else 'not_applicable' if eligible is False else 'complete' if eligible is True and value is not None else 'pending','no_declared_stockout':value,'signals':sorted(set(row_signals)),'answer_ids':sorted(set(support+(item['answer_ids'] if item else [])))}
   stores.append(row);monthly[(month,co)].append(row);annual[(month[:4],co)].append(row)
 refs=[]
 for cat,code,brand in sorted(identities):
  mapped={owners[k] for k in [perfect_store.norm(code),perfect_store.norm(brand)] if k in owners};co=next(iter(mapped)) if len(mapped)==1 and next(iter(mapped)) in companies else None
  refs.append({'category':cat,'brand_code':code,'brand':brand,'company':co,'mapping_state':'historical_company_reference' if co else 'company_not_homologated','interpretation':'Company-wide declaration among declared buyers. Not a separate brand/SKU availability measurement; category does not narrow this denominator.'})
 return {'schema':'mindtec-declared-company-availability/1','version':VERSION,'source_sha256':flat.source_sha256,'mapping_version':configuration['version'],'question_universe_version':questionnaire_scope['version'] if questionnaire_scope else None,'question_universe':questionnaire_scope,'companies':companies,'brand_references':refs,'formula':'100 * stores declaring no company stockout / stores declaring purchases from that company. Complement is declared company stockout rate.','monthly':[aggregate(rs,k[0],'month') for k,rs in sorted(monthly.items())],'annual_observed_months':[aggregate(rs,k[0],'year_observed_months_pooled_buyers') for k,rs in sorted(annual.items())],'stores':stores,'inventories':inventories,'cells':cells,'answer_evidence':answers,'limits':['Company stockout declarations are not physical SKU inventory or independent brand availability.','Brand references use historical owner mapping and share the same company result; they are not independent samples.','Explicit non-buyers are not failures or successes; unknown buying scope remains pending.','Year views pool observed store-month buyers, without annualizing or averaging monthly percentages.','No measured sales, field truth, global confidence, official-cut equivalence or fraud determination is asserted.']}
