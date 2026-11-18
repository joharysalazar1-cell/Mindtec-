"""Binary cold conversion by brand/family; operating equipment is not PS access."""
import collections,copy,math,re
import engine

VERSION='declared-cold-conversion/1.0.0'
OTHER={'otro','otros','otras_marcas','other'}

def integer(a):
 v=a.get('value')
 return int(v) if a.get('state')=='observed' and type(v) in (int,float) and math.isfinite(v) and v>=0 and float(v).is_integer() else None

def yesno(a):return a.get('value') if a.get('state')=='observed' and a.get('value') in ('si','no') else None
def token_list(a):return a['value'].split() if a.get('state')=='observed' and isinstance(a.get('value'),str) else None
def missing(route):return {'route':route,'state':'route_not_mapped','value':None,'cells':[]}
def family(cat):
 if cat.startswith('bsa_'):return 'bebidas_sin_alcohol'
 if cat.startswith('lac_'):return 'lacteos'
 raise ValueError('Explicit conversion family required')

def equipment(flat,record,rule):
 gate=flat.suffix(record,'hay_enfriadores');total=flat.suffix(record,'cuantos_enfriadores');specific=flat.suffix(record,'cuantos_enfriadores_bsa');groups=flat.groups(record,'rep_enfriador');answers=[gate,total,specific];states=[];indices=[];signals=[]
 mode=rule['equipment_rows_scope'];n=integer(total);b=integer(specific);expected=n if mode=='all_coolers' else b;g=yesno(gate)
 if mode=='all_coolers' and specific['state']!='route_not_mapped':raise ValueError('Total-equipment form unexpectedly has a BSA-specific scope')
 for name,fields in sorted(groups.items()):
  match=re.fullmatch(r'rep_enfriador\[([1-9]\d*)\]',name);indices.append(int(match[1]) if match else None);answers.extend(fields.values());on=fields.get('enfriador_encendido',missing(name+'/enfriador_encendido'));answers.append(on);states.append({'group':name,'operating':yesno(on)})
 complete=expected is not None and expected==len(groups) and set(indices)==set(range(1,expected+1))
 if not complete:signals.append('equipment_subset_enumeration_unresolved')
 if n is not None and b is not None and b>n:signals.append('bsa_equipment_count_exceeds_total')
 if expected is not None and len(groups)>expected:signals.append('equipment_rows_exceed_declared_count')
 if n is not None and len(groups)>n:signals.append('equipment_rows_exceed_total')
 if g=='no' and (groups or n not in (None,0) or b not in (None,0)):signals.append('negative_equipment_gate_with_observations')
 if g=='si' and n==0:signals.append('positive_equipment_gate_with_zero_total')
 fatal=any(s in signals for s in ['bsa_equipment_count_exceeds_total','equipment_rows_exceed_declared_count','equipment_rows_exceed_total','negative_equipment_gate_with_observations','positive_equipment_gate_with_zero_total'])
 value=None;reason='operating_state_unresolved'
 if not fatal:
  if any(s['operating']=='si' for s in states):value=1;reason='explicit_operating_equipment_exists'
  elif g=='no':value=0;reason='explicit_no_equipment'
  elif complete and n is not None and len(groups)==n and all(s['operating']=='no' for s in states):value=0;reason='all_total_equipment_explicitly_not_operating'
  else:signals.append('unlisted_or_unresolved_equipment_could_operate')
 return {'value':value,'reason':reason,'gate':g,'total_count':n,'bsa_count':b,'enumerated_count':len(groups),'enumerated_scope':mode,'subset_complete':complete,'total_enumerated':n is not None and complete and n==len(groups),'equipment':states,'signals':sorted(set(signals)),'answers':answers}

def legacy_inventory(flat,record):
 selection=flat.suffix(record,'marcas_frias_seleccionadas');count=flat.suffix(record,'n_marcas_frias');gate=flat.suffix(record,'hay_enfriadores');n=integer(count);selected=token_list(selection);groups=flat.groups(record,'rep_caras_frias');answers=[selection,count,gate];rows=[];signals=[];indices=[]
 for name,fields in sorted(groups.items()):
  answers.extend(fields.values());identity=fields.get('marca_fria_actual',missing(name+'/marca_fria_actual'));faces=fields.get('caras_frias',missing(name+'/caras_frias'));answers.extend([identity,faces]);code=identity.get('value') if identity.get('state')=='observed' and isinstance(identity.get('value'),str) else None;value=integer(faces);match=re.fullmatch(r'rep_caras_frias\[([1-9]\d*)\]',name);indices.append(int(match[1]) if match else None);rows.append({'group':name,'code':code,'faces':value})
 codes=[r['code'] for r in rows]
 if n==0 and selected is None and selection['state']=='empty_observation' and not rows:selected=[]
 if n is None or n!=len(rows) or set(indices)!=set(range(1,n+1)):signals.append('legacy_cold_enumeration_unresolved')
 if selected is None or len(selected)!=len(set(selected)) or set(selected)!=set(codes):signals.append('legacy_cold_selection_disagrees')
 if None in codes or len(codes)!=len(set(codes)):signals.append('legacy_cold_identity_unresolved_or_duplicated')
 if any(r['faces'] is None for r in rows):signals.append('legacy_cold_faces_unresolved')
 if any(c in OTHER for c in codes):signals.append('legacy_other_brand_identity_unresolved')
 for header in flat.unmapped[record['form']]:
  if re.search(r'(?:rep_caras_frias|caras_frias|marca_fria_actual|marcas_frias_seleccionadas|n_marcas_frias)',header) and record['row']['cells'][flat.columns[header]] not in (None,''):
   answers.append({'route':None,'state':'unmapped_cold_observation','value':None,'cells':[flat.cell(record,flat.columns[header])]});signals.append('unmapped_legacy_cold_observation')
 if yesno(gate)=='no' and (rows or n not in (None,0)):signals.append('negative_cooler_gate_with_cold_observations')
 return {'rows':rows,'expected':n,'selected':selected,'signals':sorted(set(signals)),'answers':answers}

def aggregate(rows,period,kind):
 base=[r for r in rows if r['eligible'] is True];unknown=sum(r['eligible'] is None for r in rows);pending=sum(r['cold'] is None for r in base);positive=sum(r['cold']==1 for r in base);complete=bool(base) and not unknown and not pending;possible=len(base)+unknown
 return {'period':period,'period_kind':kind,**{k:rows[0][k] for k in ['family','brand_code','brand']},'cohort_store_months':len(rows),'eligible_confirmed':len(base),'eligibility_pending':unknown,'cold_pending_in_eligible':pending,'known_cold_positive':positive,'known_cold_negative':sum(r['cold']==0 for r in base),'numerator':positive if complete else None,'denominator':len(base) if complete else None,'value':100*positive/len(base) if complete else None,'minimum':100*positive/possible if possible else None,'maximum':100*(positive+pending+unknown)/possible if possible else None,'state':'pending_observations' if unknown or pending else 'complete' if base else 'no_operating_brand_presence_base','months_observed':sorted({r['month'] for r in rows}),'store_rows':[r['id'] for r in rows]}

def evaluate(flat,catalog,cohort,nd,cold,scope):
 if scope.get('schema')!='mindtec-cold-conversion-scope/1' or scope.get('detailed_workbook_sha256')!=flat.source_sha256 or not isinstance(scope.get('version'),str) or not scope['version'].strip() or scope.get('unit')!='brand_within_family' or scope.get('operating_rule')!='any_reported_operating_cooler' or scope.get('negative_operating_requires_total_enumeration') is not True:raise ValueError('Source-bound explicit conversion scope required')
 if nd['source_sha256']!=flat.source_sha256 or cold['source_sha256']!=flat.source_sha256 or nd.get('source_ps_run_id')!=cold.get('source_ps_run_id') or nd.get('source_ps_snapshot_sha256')!=cold.get('source_ps_snapshot_sha256'):raise ValueError('Conversion source cuts or PS executions differ')
 cohort=list(cohort);records={(r['id'],r['month']):r for r in flat.records};forms=scope['forms']
 if not cohort or len(set(cohort))!=len(cohort) or any(k not in records for k in cohort) or set(forms)!={records[k]['form'] for k in cohort}:raise ValueError('Conversion cohort or form scope differs')
 for rule in forms.values():
  if rule.get('equipment_rows_scope') not in ('all_coolers','bsa_subset') or rule.get('cold_layout') not in ('legacy_global_brand_list','category_repetitions'):raise ValueError('Explicit per-form equipment and cold layouts required')
 identities={(c['category'],c['brand_code'],c['brand']) for c in catalog}
 if len(identities)!=len(catalog) or not identities:raise ValueError('Unique exhaustive conversion catalogue required')
 expected={(v,m,*c) for v,m in cohort for c in identities}
 def index(rows):
  out={tuple(r[k] for k in ['kobo_id','month','category','brand_code','brand']):(i,r) for i,r in enumerate(rows)}
  if len(out)!=len(rows) or set(out)!=expected:raise ValueError('Conversion source brand/store cohorts differ')
  return out
 ni=index(nd['stores']);ci=index(cold['stores']);groups=collections.defaultdict(list);families_by_code=collections.defaultdict(set)
 for cat,code,label in sorted(identities):groups[(family(cat),code,label)].append(cat);families_by_code[code].add(family(cat))
 cells={};answers={}
 for dataset in [nd,cold]:
  for name,target in [('cells',cells),('answer_evidence',answers)]:
   for key,value in dataset[name].items():
    if engine.sha(engine.canonical(value))!=key or key in target and engine.canonical(target[key])!=engine.canonical(value):raise ValueError('Conversion source evidence fingerprint differs')
    target[key]=copy.deepcopy(value)
 for answer in answers.values():
  if any(cid not in cells for cid in answer['cell_ids']):raise ValueError('Conversion answer original cell missing')
 for _,row in list(ni.values())+list(ci.values()):
  if any(aid not in answers for aid in row['answer_ids']):raise ValueError('Conversion source row answer missing')
 for key,(_,row) in ni.items():
  if row['eligible'] is not ci[key][1]['source_eligible']:raise ValueError('Cold and presence category applicability differ')
 def retain(a):
  ids=[]
  for cell in a.get('cells',[]):cid=engine.sha(engine.canonical(cell));cells[cid]=copy.deepcopy(cell);ids.append(cid)
  bound={'route':a.get('route'),'state':a['state'],'value':a.get('value'),'cell_ids':ids};aid=engine.sha(engine.canonical(bound));answers[aid]=bound;return aid
 equipment_rows=[];equipment_ids={};legacy_rows=[];legacy_ids={}
 for visit,month in sorted(cohort):
  record=records[(visit,month)];rule=forms[record['form']];inv=equipment(flat,record,rule);support=sorted({retain(a) for a in inv.pop('answers')});equipment_ids[(visit,month)]=len(equipment_rows);equipment_rows.append({'kobo_id':visit,'month':month,'form':record['form'],**inv,'answer_ids':support})
  if rule['cold_layout']=='legacy_global_brand_list':
   inv=legacy_inventory(flat,record);support=sorted({retain(a) for a in inv.pop('answers')});legacy_ids[(visit,month)]=len(legacy_rows);legacy_rows.append({'kobo_id':visit,'month':month,**inv,'answer_ids':support})
 stores=[];monthly=collections.defaultdict(list);annual=collections.defaultdict(list)
 for (fam,code,label),categories in sorted(groups.items()):
  for visit,month in sorted(cohort):
   eq=equipment_rows[equipment_ids[(visit,month)]];ns=[ni[(visit,month,c,code,label)] for c in categories];cs=[ci[(visit,month,c,code,label)] for c in categories];support=set(eq['answer_ids']);signals=[];presence=None;value=None;method='category_brand_presence'
   for _,row in ns:support.update(row['answer_ids'])
   for _,row in cs:support.update(row['answer_ids'])
   presence=1 if any(row['eligible'] is True and row['presence']==1 for _,row in ns) else None if any(row['eligible'] is None or row['eligible'] is True and row['presence'] is None for _,row in ns) else 0
   legacy_index=legacy_ids.get((visit,month));g=yesno(flat.suffix(records[(visit,month)],'hay_enfriadores'))
   if code in OTHER:signals.append('other_brand_bucket_not_an_identified_brand')
   elif legacy_index is not None:
    inv=legacy_rows[legacy_index];support.update(inv['answer_ids']);matches=[row for row in inv['rows'] if row['code']==code];method='legacy_binary_brand_presence_within_unambiguous_family'
    fatal=any(s in inv['signals'] for s in ['legacy_cold_identity_unresolved_or_duplicated','negative_cooler_gate_with_cold_observations']) or inv['expected']==0 and bool(inv['rows'])
    if fatal:signals+=inv['signals']
    elif any(row['faces'] is not None and row['faces']>0 for row in matches):
     if len(families_by_code[code])==1:value=1
     else:signals.append('legacy_cold_brand_family_ambiguous')
    elif not inv['signals']:value=0
    else:signals+=inv['signals']
   else:
    valid_positive=[row for _,row in cs if row['known_brand_faces_not_full_share'] is not None and row['known_brand_faces_not_full_share']>0]
    gate_conflict=any('negative_cooler_gate_with_cold_observations' in row['signals'] or 'zero_bsa_coolers_with_cold_observations' in row['signals'] for _,row in cs)
    if valid_positive and not gate_conflict:value=1
    elif gate_conflict:signals.append('cold_gate_contradiction')
    else:
     candidates=[ci[(visit,month,c,code,label)][1] for c in categories if ni[(visit,month,c,code,label)][1]['eligible'] is not False and ni[(visit,month,c,code,label)][1]['presence']!=0]
     if candidates and all(row['state']=='complete' and row['brand_faces']==0 for row in candidates):value=0
     else:signals.append('family_cold_presence_unresolved')
   if g=='no' and value==1:value=None;signals.append('negative_cooler_gate_with_cold_observations')
   eligible=False if presence==0 or eq['value']==0 else True if presence==1 and eq['value']==1 else None
   if presence==0 and value==1:signals.append('cold_presence_without_declared_brand_presence')
   if value==1 and eq['value']==0:signals.append('cold_count_without_operating_equipment')
   row={'id':engine.sha(engine.canonical([visit,month,fam,code,label,'cold_conversion'])),'kobo_id':visit,'month':month,'family':fam,'brand_code':code,'brand':label,'categories_referenced':categories,'presence':presence,'operating_equipment':eq['value'],'eligible':eligible,'cold':value,'state':'not_in_conversion_base' if eligible is False else 'complete' if eligible is True and value is not None else 'pending','cold_method':method,'signals':sorted(set(signals)),'equipment_index':equipment_ids[(visit,month)],'legacy_inventory_index':legacy_index,'presence_source_indices':[i for i,_ in ns],'cold_source_indices':[i for i,_ in cs],'answer_ids':sorted(support)}
   stores.append(row);monthly[(month,fam,code,label)].append(row);annual[(month[:4],fam,code,label)].append(row)
 return {'schema':'mindtec-declared-cold-conversion/1','version':VERSION,'source_sha256':flat.source_sha256,'source_ps_run_id':nd.get('source_ps_run_id'),'source_ps_snapshot_sha256':nd.get('source_ps_snapshot_sha256'),'scope_version':scope['version'],'scope':copy.deepcopy(scope),'unit':'brand_within_family','formula':'100 * stores with cold brand presence within the brand-present and operating-equipment base / stores with brand presence and at least one operating cooler.','monthly':[aggregate(rows,k[0],'month') for k,rows in sorted(monthly.items())],'annual_observed_months':[aggregate(rows,k[0],'year_observed_months_pooled_store_months') for k,rows in sorted(annual.items())],'brand_families':[{'family':f,'brand_code':c,'brand':b,'categories_referenced':cats} for (f,c,b),cats in sorted(groups.items())],'stores':stores,'equipment':equipment_rows,'legacy_cold_inventories':legacy_rows,'cells':cells,'answer_evidence':answers,'limits':['One observation per brand/family/store-month; subcategory references are not independent samples.','Legacy global faces establish binary brand presence only within an unambiguous family; faces are not partitioned into subcategories.','Operating equipment follows the observed any-cooler definition, not the PS sponsorship, exclusivity or vertical-type rule.','Partial BSA equipment lists cannot prove that all total equipment is off. A positive operating declaration proves at least one operating cooler.','Cold face counts are declarations, not measured temperature or proof that the equipment is operating.','Year views pool observed store-months; missing-data bounds are arithmetic, not confidence intervals.','No official-cut equivalence, causal inference, field validation or fraud determination is asserted.']}
