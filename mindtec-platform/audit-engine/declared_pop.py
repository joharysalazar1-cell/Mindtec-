"""Owner-company POP among declared brand-presence stores, with explicit question scope."""
import collections,copy,re
import engine,perfect_store,numeric_distribution

VERSION='declared-owner-pop/1.1.0'
UNVERIFIED={'sincorrespondenciaverificada'}

def aggregate(rows,period,kind):
 base=[r for r in rows if r['eligible'] is True and r['presence']==1]
 base_pending=[r for r in rows if r['eligible'] is None or r['eligible'] is True and r['presence'] is None]
 pending=[r for r in base if r['pop'] is None];complete=bool(base) and not base_pending and not pending
 numerator=sum(r['pop'] for r in base) if complete else None;denominator=len(base) if complete else None;positive=sum(r['pop']==1 for r in base);possible_base=len(base)+len(base_pending)
 return {'period':period,'period_kind':kind,**{k:rows[0][k] for k in ['category','brand_code','brand','company']},'cohort_store_months':len(rows),'confirmed_brand_present':len(base),'base_pending_store_months':len(base_pending),'pop_pending_in_present':len(pending),'known_pop_positive':positive,'known_pop_negative':sum(r['pop']==0 for r in base),'numerator':numerator,'denominator':denominator,'value':100*numerator/denominator if denominator else None,'minimum':100*positive/possible_base if possible_base else None,'maximum':100*(positive+len(pending)+len(base_pending))/possible_base if possible_base else None,'state':'pending_observations' if base_pending or pending else 'complete' if base else 'no_brand_presence_base','months_observed':sorted({r['month'] for r in rows}),'store_rows':[r['id'] for r in rows]}

def evaluate(flat,catalog,cohort,ps,configuration,scope):
 cohort=list(cohort);records={(r['id'],r['month']):r for r in flat.records}
 if not cohort or len(set(cohort))!=len(cohort) or any(k not in records for k in cohort):raise ValueError('Unique admitted POP visit cohort required')
 if scope.get('schema')!='mindtec-pop-question-universe/1' or scope.get('detailed_workbook_sha256')!=flat.source_sha256 or not isinstance(scope.get('version'),str) or not scope['version'].strip():raise ValueError('Source-bound versioned POP questionnaire required')
 forms=scope.get('forms',{});owners=configuration['company_by_brand'];companies=sorted((set(owners.values())|set(configuration['company_aliases'].values()))-UNVERIFIED)
 absence_policy=scope.get('unselected_owner_policy','strict_offered_owner_coverage')
 if absence_policy not in ['strict_offered_owner_coverage','confirmed_absence_in_answered_pop_section']:raise ValueError('Unknown POP absence policy')
 if absence_policy=='confirmed_absence_in_answered_pop_section' and not re.fullmatch('[0-9a-f]{64}',scope.get('absence_rule_evidence',{}).get('sha256','')):raise ValueError('Explicit user POP absence decision evidence required')
 if set(forms)!={records[k]['form'] for k in cohort}:raise ValueError('POP scope must cover exactly admitted forms')
 family_by_category={c['category']:'bebidas_sin_alcohol' if c['category'].startswith('bsa_') else 'lacteos' if c['category'].startswith('lac_') else None for c in catalog}
 if None in family_by_category.values():raise ValueError('Explicit POP category family required')
 company_families=collections.defaultdict(set)
 def owner(value):return owners.get(perfect_store.norm(value))
 for c in catalog:
  mapped={owner(v) for v in [c['brand_code'],c['brand']] if owner(v) not in (None,*UNVERIFIED)}
  if len(mapped)>1:raise ValueError('Contradictory historical POP owner')
  if mapped:company_families[next(iter(mapped))].add(family_by_category[c['category']])
 for form,q in forms.items():
  if q.get('mode')!='brands' or q.get('gate_suffix')!='tiene_material_marketing' or q.get('categories_suffix')!='categorias_material':raise ValueError('Observed brand-based POP form required')
  if set(q.get('families',{}))!={'bebidas_sin_alcohol','lacteos'} or set(q.get('category_choices',[]))!={'bebidas_sin_alcohol','lacteos','detergentes','otros'}:raise ValueError('Explicit observed family universe required')
  for family,item in q['families'].items():
   choices=item.get('choices');expected='marcas_material_bebidas' if family=='bebidas_sin_alcohol' else 'marcas_material_lacteos'
   if item.get('suffix')!=expected or not isinstance(choices,list) or not choices or len(set(choices))!=len(choices) or 'otros' not in choices:raise ValueError('Explicit unique POP choices required')
   for token in choices:
    co=owner(token)
    if co in companies:company_families[co].add(family)
 nd=numeric_distribution.evaluate(ps,catalog,cohort)
 if nd['source_sha256']!=flat.source_sha256 or configuration['version']!=ps['configuration_version']:raise ValueError('POP source PS configuration or workbook differs')
 cells=copy.deepcopy(nd['cells']);answers=copy.deepcopy(nd['answer_evidence']);inventories=[];company_rows=[];lookup={}
 def retain(answer):
  ids=[]
  for cell in answer.get('cells',[]):
   cid=engine.sha(engine.canonical(cell));cells[cid]=copy.deepcopy(cell);ids.append(cid)
  bound={'route':answer.get('route'),'state':answer['state'],'value':answer.get('value'),'cell_ids':ids};aid=engine.sha(engine.canonical(bound));answers[aid]=bound;return aid
 def tokens(answer):return answer['value'].split() if answer['state']=='observed' and isinstance(answer['value'],str) and answer['value'].strip() else None
 for visit,month in sorted(cohort):
  record=records[(visit,month)];q=forms[record['form']];gate=flat.suffix(record,q['gate_suffix']);categories=flat.suffix(record,q['categories_suffix']);other=flat.suffix(record,'material_otros_detalle');parts={f:flat.suffix(record,item['suffix']) for f,item in q['families'].items()}
  routes=set(flat.bindings[record['form']])|{r for rs in flat.ambiguous[record['form']].values() for r in rs};section=[flat.query(record,r) for r in sorted(routes) if '/registro_material_marketing/' in r];support=sorted({retain(a) for a in [gate,categories,other,*parts.values(),*section]})
  g=gate['value'] if gate['state']=='observed' and gate['value'] in ('si','no') else None;selected=tokens(categories);signals=[];observed_owners=set();uncertainty=[];family_details=[]
  descendants=[a for a in [categories,other,*parts.values(),*section] if a.get('route')!=gate.get('route')]
  active=any(c['value'] not in (None,'') for a in descendants for c in a.get('cells',[]))
  if g is None:signals.append('pop_gate_unresolved')
  if g=='no' and active:signals.append('negative_pop_gate_with_descendant_observations')
  if g=='si':
   if selected is None or len(selected)!=len(set(selected)) or any(t not in q['category_choices'] for t in selected):signals.append('pop_category_selection_unresolved')
   if selected is not None and 'otros' in selected:uncertainty.append('other_pop_category_unresolved')
   if any(c['value'] not in (None,'') for c in other.get('cells',[])):uncertainty.append('free_text_pop_not_homologated')
  for family,item in q['families'].items():
   answer=parts[family];values=tokens(answer);covered={owner(t) for t in item['choices'] if owner(t) in companies};issues=[];positive=set()
   if selected is not None and family not in selected:
    if any(c['value'] not in (None,'') for c in answer.get('cells',[])):signals.append('inactive_pop_family_with_observations')
   elif g=='si':
    if values is None:issues.append('selected_pop_family_list_unresolved')
    elif len(values)!=len(set(values)) or any(t not in item['choices'] for t in values):signals.append('pop_choice_outside_admitted_universe_or_duplicate')
    else:
     for token in values:
      co=owner(token)
      if token=='otros' or co not in companies:issues.append('pop_choice_owner_unresolved')
      else:positive.add(co)
   observed_owners.update(positive);uncertainty.extend(issues);family_details.append({'family':family,'selected':None if selected is None else family in selected,'values':values,'offered_choices':item['choices'],'covered_companies':sorted(covered),'positive_companies':sorted(positive),'signals':sorted(set(issues)),'answer_id':retain(answer)})
  signals=sorted(set(signals));uncertainty=sorted(set(uncertainty));inventory={'kobo_id':visit,'month':month,'form':record['form'],'gate':g,'selected_categories':selected,'families':family_details,'positive_companies':sorted(observed_owners),'scope_signals':signals,'negative_uncertainty':uncertainty,'answer_ids':support};inventories.append(inventory)
  for co in companies:
   value=None;reason='pop_scope_pending';row_signals=list(signals)
   if signals:pass
   elif g=='no':value=0;reason='explicit_no_marketing_material'
   elif co in observed_owners:value=1;reason='explicit_material_of_historically_owned_brand'
   elif any('selected_pop_family_list_unresolved' in f['signals'] for f in family_details):row_signals+=uncertainty;reason='selected_material_list_not_answered'
   elif absence_policy=='confirmed_absence_in_answered_pop_section':value=0;reason='confirmed_absence_by_user_rule_in_answered_section'
   elif uncertainty:row_signals+=uncertainty;reason='absence_not_supported_by_unresolved_material'
   elif not company_families[co]:row_signals.append('company_family_unresolved')
   else:
    for f in family_details:
     if f['family'] in company_families[co] and f['selected'] and co not in f['covered_companies']:row_signals.append('company_not_represented_in_offered_pop_choices')
    if not row_signals:value=0;reason='complete_admitted_family_choices_do_not_include_owner'
   row={'id':engine.sha(engine.canonical([visit,month,co,'pop'])),'kobo_id':visit,'month':month,'company':co,'value':value,'state':'complete' if value is not None else 'pending','reason':reason,'signals':sorted(set(row_signals)),'inventory_index':len(inventories)-1,'answer_ids':support};lookup[(visit,month,co)]=len(company_rows);company_rows.append(row)
 stores=[];monthly=collections.defaultdict(list);annual=collections.defaultdict(list)
 for nr in nd['stores']:
  mapped={owner(v) for v in [nr['brand_code'],nr['brand']] if owner(v) not in (None,*UNVERIFIED)};co=next(iter(mapped)) if len(mapped)==1 else None;company_index=lookup.get((nr['kobo_id'],nr['month'],co));cr=company_rows[company_index] if company_index is not None else None
  in_base=nr['eligible'] is True and nr['presence']==1;pending_base=nr['eligible'] is None or nr['eligible'] is True and nr['presence'] is None;value=cr['value'] if in_base and cr else None
  row={'id':engine.sha(engine.canonical([nr['kobo_id'],nr['month'],nr['category'],nr['brand_code'],nr['brand'],'pop'])),**{k:copy.deepcopy(nr[k]) for k in ['kobo_id','month','category','brand_code','brand','eligible','presence','category_signals']},'company':co,'company_row_index':company_index,'presence_source_id':nr['id'],'pop':value,'state':'not_in_brand_presence_base' if not in_base and not pending_base else 'complete' if value is not None else 'pending','signals':sorted(set((cr['signals'] if cr else ['brand_owner_unresolved'])+(['brand_presence_base_pending'] if pending_base else []))),'answer_ids':sorted(set(nr['answer_ids']+(cr['answer_ids'] if cr else [])))}
  stores.append(row);monthly[(nr['month'],nr['category'],nr['brand_code'],nr['brand'])].append(row);annual[(nr['month'][:4],nr['category'],nr['brand_code'],nr['brand'])].append(row)
 return {'schema':'mindtec-declared-owner-pop/1','version':VERSION,'source_sha256':flat.source_sha256,'configuration_version':configuration['version'],'question_universe_version':scope['version'],'absence_policy':absence_policy,'question_universe':copy.deepcopy(scope),'formula':'100 * brand-present stores with declared material of the historical owner company / brand-present stores; complete only with every applicable declaration and presence base resolved.','monthly':[aggregate(rows,k[0],'month') for k,rows in sorted(monthly.items())],'annual_observed_months':[aggregate(rows,k[0],'year_observed_months_pooled_brand_presence') for k,rows in sorted(annual.items())],'stores':stores,'company_rows':company_rows,'inventories':inventories,'cells':cells,'answer_evidence':answers,'limits':['Brand-based September/October forms mapped to historical company owners; not November company-form responses.','Negative declarations follow the explicitly retained absence policy. User business rules are distinguished from raw answers and official implementation. Unanswered lists and contradictions remain pending.','Presence denominator differs from category distribution and company purchasing scope.','Annual view pools observed store-months without dropping pending months or averaging percentages.','No independent field validation, official-version equivalence, causal explanation or fraud determination.']}

def findings(ps,result):
 out=[]
 for inv in result['inventories']:
  if not inv['scope_signals'] and not inv['negative_uncertainty']:continue
  informational=result.get('absence_policy')=='confirmed_absence_in_answered_pop_section' and not inv['scope_signals'] and 'selected_pop_family_list_unresolved' not in inv['negative_uncertainty']
  evidence={'source_sha256':result['source_sha256'],'absence_policy':result.get('absence_policy'),'kobo_id':inv['kobo_id'],'month':inv['month'],'form':inv['form'],'scope_signals':inv['scope_signals'],'negative_uncertainty':inv['negative_uncertainty'],'answer_ids':inv['answer_ids']};f={'rule':'pop_material_scope_unresolved','rule_version':VERSION,'severity':'info' if informational else 'medium','title':'Material adicional sin empresa atribuida' if informational else 'Universo o declaración de material POP por revisar','evidence':evidence,'explanation':'Otros y textos se conservan sin atribuirlos a empresas por suposición. Según la regla explícita del usuario, una sección respondida sin material registrado de la empresa cuenta como ausencia confirmada; esta nota no bloquea ese cero ni implica fraude.' if informational else 'La sección seleccionada sin respuesta o contradictoria permanece pendiente. Conservar las respuestas originales y la regla de ausencia del usuario; no convertir una falta de respuesta en cero ni decidir fraude.','disposition':'unassigned_material_preserved' if informational else 'needs_human_review'};f['fingerprint']=engine.sha(engine.canonical(f));out.append(f)
 lookup={(r['kobo_id'],r['month'],r['company']):r for r in result['company_rows']};groups={}
 for index,row in enumerate(ps['details']):
  cr=lookup.get((row['kobo_id'],row['month'],row['company']));comp=next(c for c in row['components'] if c['component']=='POP')
  if cr and comp['state']=='measured' and (cr['value'] is None or cr['value']!=comp['value']):
   key=(row['kobo_id'],row['month'],row['company']);g=groups.setdefault(key,{'kobo_id':key[0],'month':key[1],'company':key[2],'ps_detail_indices':[],'previous_complete_scores':0,'company_value':cr['value'],'signals':cr['signals'],'answer_ids':cr['answer_ids']});g['ps_detail_indices'].append(index);g['previous_complete_scores']+=row['score'] is not None
 for evidence in groups.values():
  evidence.update(source_sha256=result['source_sha256'],source_ps_run_id=result.get('source_ps_run_id'),source_ps_snapshot_sha256=result.get('source_ps_snapshot_sha256'));f={'rule':'ps_pop_company_scope_not_supported','rule_version':VERSION,'severity':'medium','title':'Componente POP histórico de Perfect Store por revisar','evidence':evidence,'explanation':'El valor histórico medido no coincide con la reconstrucción que exige categorías, opciones y propietarios resueltos. Mantener la versión previa y revisar su respaldo antes de cambiar puntajes; no se modifica PS ni se presume fraude.','disposition':'methodological_review_required'};f['fingerprint']=engine.sha(engine.canonical(f));out.append(f)
 return out
