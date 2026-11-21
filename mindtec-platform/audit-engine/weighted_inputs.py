"""Audit declared-purchase and observed-size inputs; never invent official DP weights."""
import collections,copy,re
import engine,cold_conversion as cold,purchase_binding

VERSION='weighted-input-readiness/1.1.0'


def cooling_doors(flat,record,equipment_scope):
 eq=cold.equipment(flat,record,{'equipment_rows_scope':equipment_scope});answers=eq.pop('answers');known=0;pending=0;rows=[]
 for name,fields in sorted(flat.groups(record,'rep_enfriador').items()):
  on=fields.get('enfriador_encendido',cold.missing(name+'/enfriador_encendido'));doors=fields.get('puertas_enfriador',cold.missing(name+'/puertas_enfriador'));answers.extend([on,doors]);operation=cold.yesno(on);n=cold.integer(doors)
  contribution=0 if operation=='no' or n==0 else n if operation=='si' and n is not None else None
  if contribution is None:pending+=1
  else:known+=contribution
  rows.append({'group':name,'operating':operation,'doors':n,'known_contribution':contribution})
 no_equipment=eq['reason']=='explicit_no_equipment';covered=eq['total_enumerated'] or no_equipment
 contradictions=set(eq['signals']) & {'bsa_equipment_count_exceeds_total','equipment_rows_exceed_declared_count','equipment_rows_exceed_total','negative_equipment_gate_with_observations','positive_equipment_gate_with_zero_total'}
 complete=covered and not pending and not contradictions
 signals=list(eq['signals'])
 if not covered:signals.append('total_equipment_not_enumerated')
 if pending:signals.append('cooling_door_contribution_unresolved')
 return {'value':known if complete else None,'known_subtotal_not_total':known,'state':'complete' if complete else 'pending','total_equipment_covered':covered,'pending_equipment_rows':pending,'signals':sorted(set(signals)),'equipment_rows':rows,'answers':answers}


def purchase_declarations(flat,record,bindings=None):
 if bindings is not None:purchase_binding.validate(bindings,flat)
 selection=flat.suffix(record,'empresas_compra');count=flat.suffix(record,'n_empresas_compra');answers=[selection,count];selected=cold.token_list(selection);n=cold.integer(count);rows=[];indices=[];codes=[]
 for name,fields in sorted(flat.groups(record,'rep_empresa_compra').items()):
  match=re.fullmatch(r'rep_empresa_compra\[([1-9]\d*)\]',name);indices.append(int(match[1]) if match else None)
  wanted=[fields.get(k,cold.missing(name+'/'+k)) for k in ['empresa_actual','monto_compra_empresa','frecuencia_compra_empresa']];binding=None
  if bindings is not None:
   original=wanted[1];wanted[1],binding=purchase_binding.resolve(flat,record,name,original,bindings)
   if binding is not None:answers.append(original)
  answers.extend(wanted);code=wanted[0]['value'] if wanted[0]['state']=='observed' else None;codes.append(code)
  rows.append({'group':name,'company':code,'amount_state':wanted[1]['state'],'amount_raw':wanted[1]['value'],'amount_binding':binding,'frequency_state':wanted[2]['state'],'frequency_raw':wanted[2]['value']})
 complete=n is not None and n==len(rows) and set(indices)==set(range(1,n+1)) and selected is not None and len(selected)==len(set(selected))==len(codes) and set(selected)==set(codes) and all(c is not None for c in codes)
 raw_amounts=[]
 for index,header in enumerate(flat.headers):
  if 'equivale cada compra de productos de ${empresa_label}?' not in header:continue
  cell=flat.cell(record,index)
  if cell['value'] in (None,''):continue
  raw_amounts.append({'header':header,'value':cell['value'],'coordinate':cell['coordinate'],'historical_route_assigned':any(r['amount_binding'] is not None and r['amount_binding']['coordinate']==cell['coordinate'] for r in rows)})
  answers.append({'route':None,'state':'original_purchase_amount_header_observation','value':cell['value'],'cells':[cell]})
 return {'selected_companies':selected,'declared_company_count':n,'enumeration_complete':complete,'rows':rows,'original_amount_header_observations':raw_amounts,'monthly_category_purchase':None,'state':'category_purchase_rule_unresolved','signals':['category_allocation_not_exported','range_to_weight_mapping_not_exported','frequency_to_month_mapping_not_exported','purchase_and_size_weight_normalization_not_exported']+([] if complete else ['company_purchase_enumeration_unresolved'])+(['unmapped_purchase_amount_cells_preserved'] if raw_amounts and any(r['amount_state']=='route_not_mapped' for r in rows) else []),'answers':answers}


def evaluate(flat,shelf,conversion,bindings=None):
 if bindings is not None:purchase_binding.validate(bindings,flat)
 if shelf['source_sha256']!=flat.source_sha256 or conversion['source_sha256']!=flat.source_sha256 or any(shelf.get(k)!=conversion.get(k) for k in ['source_ps_run_id','source_ps_snapshot_sha256']):raise ValueError('Weighted-input source cuts or executions differ')
 visits={(r['kobo_id'],r['month']) for r in conversion['equipment']};records={(r['id'],r['month']):r for r in flat.records}
 if len(visits)!=len(conversion['equipment']) or not visits or not visits<=set(records):raise ValueError('Unique admitted weighted-input visits required')
 cells={};answers={}
 for source in [shelf,conversion]:
  for name,target in [('cells',cells),('answer_evidence',answers)]:
   for key,value in source[name].items():
    if engine.sha(engine.canonical(value))!=key or key in target and target[key]!=value:raise ValueError('Weighted-input source evidence differs')
    target[key]=copy.deepcopy(value)
 def retain(a):
  ids=[]
  for c in a.get('cells',[]):
   cid=engine.sha(engine.canonical(c));cells[cid]=copy.deepcopy(c);ids.append(cid)
  bound={'route':a.get('route'),'state':a['state'],'value':a.get('value'),'cell_ids':ids};aid=engine.sha(engine.canonical(bound));answers[aid]=bound;return aid
 equipment=[];purchases=[];visit_index={}
 for key in sorted(visits):
  r=records[key];mode=conversion['scope']['forms'][r['form']]['equipment_rows_scope'];item=cooling_doors(flat,r,mode);p=purchase_declarations(flat,r,bindings);visit_index[key]=len(equipment)
  for data,target in [(item,equipment),(p,purchases)]:
   support=sorted({retain(a) for a in data.pop('answers')});target.append({'kobo_id':key[0],'month':key[1],'form':r['form'],**data,'answer_ids':support})
 rows=[];seen=set();categories={inv['category'] for inv in shelf['category_inventories']}
 for source_index,inv in enumerate(shelf['category_inventories']):
  visit=(inv['kobo_id'],inv['month']);key=(*visit,inv['category'])
  if visit not in visits or key in seen:raise ValueError('Weighted-input category cohort differs')
  seen.add(key);i=visit_index[visit];eq=equipment[i];faces=inv['faces'] if inv['state']=='complete' else None;value=faces+4*eq['value'] if faces is not None and eq['value'] is not None else None
  support=sorted(set(inv['answer_ids'])|set(eq['answer_ids'])|set(purchases[i]['answer_ids']))
  if any(a not in answers for a in support):raise ValueError('Weighted-input support missing')
  rows.append({'kobo_id':visit[0],'month':visit[1],'category':inv['category'],'eligible':inv['eligible'],'shelf_inventory_index':source_index,'equipment_index':i,'purchase_index':i,'category_faces':faces,'known_category_faces_not_total':inv.get('known_faces_subtotal_not_total'),'total_cooling_doors':eq['value'],'observed_size_candidate':value,'size_components_state':'complete' if value is not None else 'pending','official_weight':None,'official_weight_state':'weighting_rule_pending','answer_ids':support})
 if seen!={(*v,c) for v in visits for c in categories}:raise ValueError('Weighted-input category visits omitted')
 for a in answers.values():
  if any(cid not in cells for cid in a['cell_ids']):raise ValueError('Weighted-input original cell missing')
 readiness=[]
 for month,cat in sorted({(r['month'],r['category']) for r in rows}):
  group=[r for r in rows if r['month']==month and r['category']==cat];eligible=[r for r in group if r['eligible'] is True]
  readiness.append({'month':month,'category':cat,'cohort_store_months':len(group),'eligible_confirmed':len(eligible),'eligibility_pending':sum(r['eligible'] is None for r in group),'eligible_with_complete_size_components':sum(r['size_components_state']=='complete' for r in eligible),'official_weight_state':'weighting_rule_pending'})
 return {'schema':'mindtec-weighted-input-readiness/1','version':VERSION,'source_sha256':flat.source_sha256,'source_ps_run_id':shelf.get('source_ps_run_id'),'source_ps_snapshot_sha256':shelf.get('source_ps_snapshot_sha256'),'equipment':equipment,'purchase_declarations':purchases,'category_stores':rows,'monthly_readiness':readiness,'cells':cells,'answer_evidence':answers,'limits':['Input readiness is not a reconstructed DP percentage or an official weight.','Observed size candidate is category faces plus four times all reported cooling doors; category/family applicability of doors remains to be fixed.','Company purchase ranges and frequencies remain original tokens. No midpoint, upper cap, monthly factor or category allocation is invented.','Combining purchase-based and size-based weights requires the compatible official normalization and fallback rules.','Incomplete total equipment enumeration does not establish a total of cooling doors.','No source answers changed, invoices substituted, field truth validated or fraud determined.']}
