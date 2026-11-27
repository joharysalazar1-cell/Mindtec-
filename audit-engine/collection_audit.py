"""Audit a normalized collection result cut without substituting it for raw Scan answers."""
import collections,math
from pathlib import Path
import engine
from collection_adapter import table_rows

VERSION='collection-result-audit/1.0.0'
IMPLEMENTATION_BYTES=Path(__file__).read_bytes()
SHEETS={'visits':'Envíos','shops':'Colecta · tiendas','brands':'Colecta · marcas','prices':'Colecta · precios','companies':'Colecta · empresas'}

def identifier(v):
 if isinstance(v,bool) or v is None:return None
 if isinstance(v,(int,float)):
  if not math.isfinite(v) or not float(v).is_integer():return None
  return str(int(v))
 return str(v).strip() or None

def numeric(v,integer=False,positive=False):return not isinstance(v,bool) and isinstance(v,(int,float)) and math.isfinite(v) and (not integer or v>=0 and float(v).is_integer()) and (not positive or v>0)

def tables(cut):
 if cut.get('schema')!='mindtec-collection-result-cut/1' or cut.get('identity_namespace')!='scan_internal_envio_id':raise ValueError('Normalized result-cut contract required')
 by_name={t['sheet']:t for t in cut['tables']}
 if len(by_name)!=len(cut['tables']):raise ValueError('Repeated worksheet identity')
 return {role:{'table':by_name[name],'rows':table_rows(by_name[name])} for role,name in SHEETS.items()}

def cell_ref(table,row,column):
 at=table['headers'].index(column);letters=''.join(c for c in table['header_coordinates'][at] if c.isalpha())
 return {'sheet':table['sheet'],'source_row':row['source_row'],'column':column,'coordinate':row['coordinates'].get(column) or letters+str(row['source_row']),'value':row['values'].get(column),'internal_id':identifier(row['values'].get('ID envío'))}

def row_key(role,row):
 v=row['values'];eid=identifier(v.get('ID envío'))
 if not eid:return None
 if role in ('visits','shops'):return (eid,)
 month=v.get('Mes')
 if not isinstance(month,str) or not month:return None
 if role=='brands':
  code=v.get('Marca (código)');category=v.get('Subcategoría (código)')
  if not category or not code:return None
  return (eid,month,category,code,v.get('Marca') if str(code).lower() in ('otro','otras','otras_marcas','other') else '')
 if role=='prices':
  code=v.get('Código Kobo');where=v.get('Dónde')
  return (eid,month,where,code) if code and where else None
 code=v.get('Empresa (código)');return (eid,month,code) if code else None

def evaluate(current,previous=None,crosswalk=None,policy=None):
 now=tables(current);old=tables(previous) if previous else None;findings=[];changes=[];schema_changes=[];crosswalk=crosswalk or {};policy=policy or {'exclusions':[]}
 exclusions={str(e['id']):e for e in policy.get('exclusions',[])}
 def emit(rule,severity,role,row,columns,observed,explanation):
  refs=[cell_ref(now[role]['table'],row,c) for c in columns]
  ev={'internal_id':identifier(row['values'].get('ID envío')),'source_sha256':current['provenance']['original_sha256'],'cells':refs,'observed':observed}
  f={'rule':rule,'rule_version':'1','severity':severity,'title':rule.replace('_',' '),'evidence':ev,'explanation':explanation,'disposition':'needs_human_review'};f['fingerprint']=engine.sha(engine.canonical({'rule':rule,'version':'1','evidence':ev}));findings.append(f)
 indexed={}
 for role,entry in now.items():
  groups=collections.defaultdict(list)
  for row in entry['rows']:
   key=row_key(role,row)
   if key is None:emit('incomplete_row_identity','medium',role,row,['ID envío'],None,'La fila no tiene una clave completa para comparar; no se elige otra fila por similitud.')
   else:groups[key].append(row)
  indexed[role]=groups
  for key,rows in groups.items():
   if len(rows)>1:emit('ambiguous_row_identity','medium',role,rows[0],['ID envío'],{'key':key,'source_rows':[r['source_row'] for r in rows]},'Clave repetida; se conserva el grupo y no se empareja ni deduplica automáticamente.')
 parents={k[0]:rows[0] for k,rows in indexed['visits'].items() if len(rows)==1}
 current_ids=set(parents);excluded=[];unmapped=[]
 for eid,row in parents.items():
  kobo=crosswalk.get(eid)
  if kobo is None:
   unmapped.append(eid)
   emit('identity_crosswalk_missing','medium','visits',row,['ID envío'],eid,'No hay correspondencia inequívoca con ID Kobo. Se conserva la visita, pero no entra en cálculos sujetos a exclusiones históricas.')
  if kobo in exclusions:
   excluded.append({'internal_id':eid,'kobo_id':kobo,'reason':exclusions[kobo]['reason'],'source_row':row['source_row']})
   if row['values'].get('Estado de entrega')=='LISTO':emit('historical_exclusion_in_ready_export','medium','visits',row,['ID envío','Estado de entrega'],{'kobo_id':kobo,'historical_reason':exclusions[kobo]['reason']},'El estado de entrega no revoca por sí solo la exclusión histórica. Requiere decisión motivada antes de cambiar la cohorte.')
 # Without the identity crosswalk the historical exclusions cannot be applied.
 # Keep unknown IDs in the evidence, but never silently call them eligible.
 eligible=current_ids-{e['internal_id'] for e in excluded}-set(unmapped)
 for role,entry in now.items():
  if role=='visits':continue
  for row in entry['rows']:
   eid=identifier(row['values'].get('ID envío'));parent=parents.get(eid)
   if not parent:emit('missing_unique_parent','high',role,row,['ID envío'],eid,'No hay un envío padre único; comprobar ID y tablas de la exportación.');continue
   for field in ['Mes','Sticker']:
    if row['values'].get(field)!=parent['values'].get(field):emit('parent_field_disagrees','medium',role,row,['ID envío',field],{'child':row['values'].get(field),'parent':parent['values'].get(field)},'Campo distinto entre tablas del mismo archivo. Conservar ambos; no corregir silenciosamente.')
 for eid,parent in parents.items():
  if len(indexed['shops'].get((eid,),[]))!=1:emit('shop_detail_missing_or_ambiguous','medium','visits',parent,['ID envío'],None,'Se requiere una fila única de detalle de tienda.')
 for row in now['brands']['rows']:
  for field in ['Caras en góndola','Caras en frío']:
   value=row['values'].get(field)
   if not numeric(value,integer=True):emit('invalid_or_missing_face_count','medium','brands',row,[field],value,'Se esperan conteos enteros no negativos. Vacío no equivale a cero; la participación afectada queda sin calcular.')
 for row in now['prices']['rows']:
  value=row['values'].get('Precio Bs')
  if not numeric(value,positive=True):emit('price_requires_interpretation','medium','prices',row,['Precio Bs'],value,'Precio ausente, no numérico o no positivo. Confirmar registro/unidad; no atribuye manipulación.')
  if row['values'].get('ID SKU') in (None,''):emit('price_without_master_sku','medium','prices',row,['Código Kobo','ID SKU','SKU (maestro)'],None,'El SKU de maestro no está resuelto. No homologar otro producto por parecido del nombre.')
 for row in now['companies']['rows']:
  if row['values'].get('Quiebre') not in ('si','no'):emit('stock_answer_not_resolved','info','companies',row,['Empresa (código)','Quiebre'],row['values'].get('Quiebre'),'No se usa una respuesta ausente o fuera del catálogo como si significara ausencia de quiebre.')
 matched_counts={};numeric_pairs=collections.defaultdict(list)
 if old:
  for role,entry in now.items():
   old_index=collections.defaultdict(list)
   for row in old[role]['rows']:
    key=row_key(role,row)
    if key is not None:old_index[key].append(row)
   old_headers=old[role]['table']['headers'];new_headers=entry['table']['headers'];shared=[h for h in new_headers if h in old_headers]
   if set(old_headers)!=set(new_headers):schema_changes.append({'sheet':entry['table']['sheet'],'new_columns':[h for h in new_headers if h not in old_headers],'absent_columns':[h for h in old_headers if h not in new_headers]})
   counts={'matched_unique':0,'current_only_in_matched_visits':0,'previous_only_in_matched_visits':0,'ambiguous_keys':0,'changed_cells':0}
   for key in sorted(set(old_index)|set(indexed[role]),key=engine.canonical):
    before=old_index.get(key,[]);after=indexed[role].get(key,[])
    if key[0] not in current_ids:continue
    if len(before)>1 or len(after)>1:counts['ambiguous_keys']+=1;continue
    if not before or not after:
     state='current_only_in_matched_visits' if after else 'previous_only_in_matched_visits';counts[state]+=1
     changes.append({'kind':state,'sheet':entry['table']['sheet'],'internal_id':key[0],'key':key,'before_row':before[0]['source_row'] if before else None,'after_row':after[0]['source_row'] if after else None,'explanation':'Presencia de fila en la exportación de las mismas visitas; no demuestra alta/baja real de producto.'});continue
    a,b=before[0],after[0];counts['matched_unique']+=1
    for field in shared:
     av,bv=a['values'].get(field),b['values'].get(field)
     if role=='brands' and field in ['Caras en góndola','Caras en frío'] and numeric(av,integer=True) and numeric(bv,integer=True):numeric_pairs['brands:'+field].append(bv-av)
     if role=='prices' and field=='Precio Bs' and numeric(av,positive=True) and numeric(bv,positive=True):numeric_pairs['prices:Precio Bs'].append(bv-av)
     if engine.canonical(av)!=engine.canonical(bv):
      counts['changed_cells']+=1;changes.append({'kind':'cell_changed','sheet':entry['table']['sheet'],'internal_id':key[0],'key':key,'field':field,'before':cell_ref(old[role]['table'],a,field),'after':cell_ref(entry['table'],b,field),'explanation':'Valor distinto entre archivos. La revisión o normalización puede explicar el cambio; no se deduce el motivo ni fraude.'})
   matched_counts[role]=counts
 cat_rows=collections.defaultdict(list);brand_rows=collections.defaultdict(list)
 eligible_by_month=collections.defaultdict(set)
 for eid in eligible:eligible_by_month[parents[eid]['values'].get('Mes')].add(eid)
 for row in now['brands']['rows']:
  v=row['values'];eid=identifier(v.get('ID envío'))
  if eid not in eligible:continue
  month=v.get('Mes');cat=v.get('Subcategoría (código)');brand=(month,cat,str(v.get('Marca (código)') or ''),str(v.get('Marca') or ''))
  if month!=parents[eid]['values'].get('Mes'):continue
  cat_rows[(month,cat)].append(row);brand_rows[brand].append(row)
 metrics=[]
 for (month,category,code,name),rows in sorted(brand_rows.items(),key=lambda x:engine.canonical(x[0])):
  cohort=eligible_by_month[month]
  values={'month':month,'category':category,'brand_code':code,'brand':name,'observed_visits':len({identifier(r['values'].get('ID envío')) for r in rows}),'cohort_visits':len(cohort),'scope':'exported_ready_visits_under_historical_exclusions','source_rows':[r['source_row'] for r in rows],'denominator_visit_ids':sorted(cohort),'measures':{}}
  for field,key in [('Caras en góndola','shelf_faces'),('Caras en frío','cold_faces')]:
   denominator_rows=cat_rows[(month,category)];complete=all(numeric(r['values'].get(field),integer=True) and len(indexed['brands'].get(row_key('brands',r),[]))==1 for r in denominator_rows)
   numerator=sum(r['values'][field] for r in rows) if complete else None;denominator=sum(r['values'][field] for r in denominator_rows) if complete else None
   valid_rows=[r for r in denominator_rows if numeric(r['values'].get(field),integer=True) and len(indexed['brands'].get(row_key('brands',r),[]))==1]
   values['measures'][key]={'numerator':numerator,'denominator':denominator,'share_pct':100*numerator/denominator if denominator else None,'state':'measured_in_export' if denominator else 'zero_category_denominator' if denominator==0 else 'incomplete_or_ambiguous_faces','valid_category_rows':len(valid_rows),'category_rows':len(denominator_rows),'registered_subtotal':sum(r['values'][field] for r in valid_rows),'missing_or_ambiguous_rows':[r['source_row'] for r in denominator_rows if r not in valid_rows],'numerator_cells':[cell_ref(now['brands']['table'],r,field) for r in rows],'denominator_cells':[cell_ref(now['brands']['table'],r,field) for r in denominator_rows]}
  metrics.append(values)
 company_rows=collections.defaultdict(list)
 for row in now['companies']['rows']:
  eid=identifier(row['values'].get('ID envío'));month=row['values'].get('Mes')
  if eid in eligible and row_key('companies',row) and month==parents[eid]['values'].get('Mes'):company_rows[(month,row['values'].get('Empresa (código)'),row['values'].get('Empresa'))].append(row)
 companies=[]
 for (month,code,name),rows in sorted(company_rows.items(),key=lambda x:engine.canonical(x[0])):
  measured=[r for r in rows if r['values'].get('Quiebre') in ('si','no') and len(indexed['companies'].get(row_key('companies',r),[]))==1];no=sum(r['values']['Quiebre']=='no' for r in measured)
  companies.append({'month':month,'company_code':code,'company':name,'observed_visits':len({identifier(r['values'].get('ID envío')) for r in rows}),'stock_answered_rows':len(measured),'no_stockout_rows':no,'no_stockout_pct':100*no/len(measured) if measured else None,'stock_cells':[cell_ref(now['companies']['table'],r,'Quiebre') for r in rows],'scope':'declared_company_stockout_not_sku_availability'})
 previous_ids={identifier(r['values'].get('ID envío')) for r in old['visits']['rows']} if old else set()
 previous_same_month_ids={identifier(r['values'].get('ID envío')) for r in old['visits']['rows'] if r['values'].get('Mes') in {r['values'].get('Mes') for r in parents.values()}} if old else set()
 summaries={name:{'pairs':len(ds),'bias_after_minus_before':sum(ds)/len(ds),'mae_change':sum(abs(v) for v in ds)/len(ds),'rmse_change':math.sqrt(sum(v*v for v in ds)/len(ds)),'max_absolute_change':max(abs(v) for v in ds),'interpretation':'Changes between retained files, not error against ground truth or panel.'} for name,ds in numeric_pairs.items() if ds}
 indicator_status=[{'indicator':name,'state':state,'definition':definition,'missing':missing} for name,state,definition,missing in [
  ('Perfect Store','not_reconstructible_from_this_export','Requiere elegibilidad por subcategoría y los cinco componentes aplicables por tienda.','Detalle de equipo accesible/operativo, POP por empresa y canasta SKU/configuración vigente; faltan septiembre y visitas pendientes.'),
  ('Distribución numérica','observed_coverage_only','Se cuenta presencia registrada sobre visitas incluidas; no equivale al universo oficial por categoría.','Elegibilidad y universo completo del mes.'),
  ('Distribución ponderada','not_reconstructible','Requiere pesos de cada tienda y universo definido.','Pesos de tienda y base de ponderación; no hay facturas en este archivo.'),
  ('Share de estante','measured_in_partial_export','Suma de caras registradas de la marca / suma de caras registradas de la categoría.','Resultado limitado a las visitas incluidas; no comparable al panel completo.'),
  ('Share en enfriador','measured_in_partial_export','Suma de caras frías registradas de la marca / suma de caras frías registradas de la categoría.','Sin vínculo con equipos ni acceso; denominador cero no se convierte en 0%.'),
  ('Conversión a frío','not_reconstructible','Requiere disponibilidad de equipo operativo accesible para cada marca.','Detalle individual de enfriadores, patrocinio, funcionamiento y aplicabilidad.'),
  ('Disponibilidad','company_proxy_only','Se conserva declaración de quiebre por empresa; no es inventario de SKU.','Universo por empresa/tienda; regla oficial si se pretende contraste con el panel.'),
  ('Visibilidad POP','not_reconstructible','Material de marketing agregado no identifica inequívocamente marca/empresa.','Presencia POP por marca/empresa y aplicabilidad.'),
  ('Cumplimiento SKU núcleo','not_reconstructible','La lista observada de SKU no define qué referencias eran obligatorias.','Matriz núcleo por marca, canal, mes y versión.'),
  ('Fair share','not_reconstructible','Requiere base objetivo y cociente oficial documentados.','Objetivo/participación esperada y versión de regla.'),
  ('Índice de precio','prices_only','Se auditan precios originales y sus cambios; no se inventa un precio objetivo.','Precios de referencia, SKU equivalentes, unidad y regla/versionado.'),
  ('Índice de ejecución MindTEC','not_reconstructible','Depende de componentes, pesos y reglas de agregación.','Configuración completa y aplicabilidad/versionado.')]]
 return {'schema':'mindtec-collection-result-audit/1','version':VERSION,'source':current['provenance'],'previous_source':previous['provenance'] if previous else None,'coverage':{'months':dict(collections.Counter(str(r['values'].get('Mes')) for r in parents.values())),'delivery_states':dict(collections.Counter(str(r['values'].get('Estado de entrega')) for r in parents.values())),'exported_visits':len(parents),'historical_policy_eligible_visits':len(eligible),'excluded':excluded,'unmapped_internal_ids':unmapped,'current_ids':sorted(current_ids),'matched_previous_ids':len(current_ids&previous_ids),'previous_same_month_visits':len(previous_same_month_ids),'previous_same_month_not_in_export':sorted(previous_same_month_ids-current_ids),'missing_month_is_not_deletion':True},'table_counts':{k:len(v['rows']) for k,v in now.items()},'schema_changes':schema_changes,'comparison_counts':matched_counts,'numeric_change_statistics':summaries,'findings':findings,'changes':changes,'brand_metrics':metrics,'company_metrics':companies,'indicators':indicator_status,'limits':['Only the received workbook is the updated source; historical cuts remain separate.','No September rows are inferred when missing.','LISTO is a delivery state, not a probability of correctness.','Original normalized results are not a complete raw-answer export.','Historical exclusions remain unless a documented decision changes them.','Chi-square not applied: paired corrected observations and different export coverage do not establish independent random samples.','No inference of fraud or automatic sanctions.']}
