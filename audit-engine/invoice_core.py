"""Invoice quality and comparable-cut differences, without inferred tax rules."""
import collections,datetime as dt,decimal,hashlib,json,math,re
from engine import canonical,sha

VERSION='invoice-py/1.0.1'
NUMERIC_FIELDS={'Cantidad','Precio unitario','Descuento línea','Bonificación línea','ICE línea','Total neto','Subtotal factura','Descuento factura','Bonificación factura','ICE factura','Total factura','Monto Kobo','Diferencia','Unidades','Litros','Bs por unidad'}
def empty(v):return v is None or isinstance(v,str) and not v.strip()
def number(v):
 if isinstance(v,bool) or not isinstance(v,(int,float,str)) or empty(v):return None
 try:
  n=decimal.Decimal(str(v));return n if n.is_finite() else None
 except decimal.InvalidOperation:return None
def date(v,system):
 if empty(v):return None
 try:
  if isinstance(v,(int,float)) and not isinstance(v,bool) and system=='excel_1900' and math.isfinite(v):
   if v<1 or int(v)==60:return None
   return (dt.datetime(1899,12,30)+dt.timedelta(days=v if v>=61 else v+1)).date()
  if isinstance(v,str):return dt.date.fromisoformat(v[:10])
 except (ValueError,OverflowError):pass
 return None
def validate_cut(cut):
 if not isinstance(cut,dict) or cut.get('schema')!='mindtec-invoice-cut/1':raise ValueError('Invoice cut schema required')
 if not isinstance(cut.get('headers'),list) or not cut['headers'] or len(set(cut['headers']))!=len(cut['headers']) or not all(isinstance(h,str) and h for h in cut['headers']):raise ValueError('Unique source headers required')
 for h in ['ID factura','Línea','Mes','Sticker','Total neto']:
  if h not in cut['headers']:raise ValueError('Missing source field: '+h)
 if all(h in cut['headers'] for h in ['N.º documento','N.° documento']):raise ValueError('Ambiguous document-number headers; provide an explicit mapping')
 scope=cut.get('scope')
 if not isinstance(scope,dict) or not all(isinstance(scope.get(k),str) and scope[k].strip() for k in ['namespace','currency','period_basis','cohort_id']):raise ValueError('Explicit namespace, currency, period basis and cohort required')
 if not isinstance(scope.get('periods'),list) or not scope['periods'] or any(not isinstance(m,str) or re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])',m) is None for m in scope['periods']):raise ValueError('Observation periods required')
 if not isinstance(cut.get('rows'),list) or not cut['rows']:raise ValueError('Empty cuts are not accepted')
 source_rows=set()
 for r in cut['rows']:
  if not isinstance(r,dict) or not isinstance(r.get('cells'),list) or len(r['cells'])!=len(cut['headers']) or not isinstance(r.get('source_row'),int) or isinstance(r['source_row'],bool) or r['source_row']<2:raise ValueError('Each source row needs aligned cells and Excel row')
  if r['source_row'] in source_rows:raise ValueError('Duplicate Excel source row')
  source_rows.add(r['source_row'])
 return cut
def validate_policy(p):
 if p.get('schema')!='mindtec-invoice-policy/1' or not isinstance(p.get('version'),str) or not p['version'].strip():raise ValueError('Invoice policy version required')
 for field in ['line_arithmetic','invoice_sum']:
  cfg=p.get(field)
  if cfg is not None:
   if not isinstance(cfg,dict) or not isinstance(cfg.get('evidence'),str) or not cfg['evidence'].strip():raise ValueError('Declared formula requires evidence')
   tolerance=number(cfg.get('tolerance'))
   if tolerance is None or tolerance<0:raise ValueError('Explicit nonnegative tolerance required')
   if field=='line_arithmetic':
    if not all(isinstance(cfg.get(k),str) and cfg[k] for k in ['quantity','unit_price','target']):raise ValueError('Formula fields required')
    for k in ['deductions','additions']:
     if not isinstance(cfg.get(k),list) or not all(isinstance(v,str) and v for v in cfg[k]):raise ValueError('Explicit formula terms required')
    terms=[cfg['quantity'],cfg['unit_price'],cfg['target'],*cfg['deductions'],*cfg['additions']]
    if len(terms)!=len(set(terms)):raise ValueError('Formula must not double count fields')
   else:
    if not all(isinstance(cfg.get(k),str) and cfg[k] for k in ['target','line_field']) or not isinstance(cfg.get('complete_invoices'),dict) or not all(isinstance(v,str) and v.strip() for v in cfg['complete_invoices'].values()):raise ValueError('Invoice completeness needs per-document evidence')
 return p
def row_values(cut):return [dict(zip(cut['headers'],r['cells'])) for r in cut['rows']]
def line_key(v):
 if empty(v.get('ID factura')) or empty(v.get('Línea')) or isinstance(v.get('ID factura'),bool) or isinstance(v.get('Línea'),bool):return None
 line=v['Línea'];line=str(int(line)) if isinstance(line,(int,float)) and not isinstance(line,bool) and math.isfinite(line) and int(line)==line else str(line)
 return str(v['ID factura'])+'|'+line
def evaluate(cut,policy,reference=None,source_hash=None,reference_hash=None):
 validate_cut(cut);validate_policy(policy)
 if reference is not None:validate_cut(reference)
 values=row_values(cut);findings=[];keys=collections.defaultdict(list);invoices=collections.defaultdict(list)
 coverage={'rows':len(values),'line_arithmetic_eligible':0,'invoice_sum_eligible':0,'line_arithmetic_configured':policy.get('line_arithmetic') is not None,'invoice_sum_configured':policy.get('invoice_sum') is not None,'comparison_requested':reference is not None,'comparison_comparable':None,'matched_unique_keys':0,'ambiguous_comparison_keys':0}
 def emit(rule,severity,indices,fields,observed,explanation,previous=None):
  ids=[line_key(values[i]) for i in indices];record_id=ids[0] if ids and ids[0] else 'source-row:'+str(cut['rows'][indices[0]]['source_row']) if indices else str(observed.get('key','cut')) if isinstance(observed,dict) else 'cut'
  ev={'record_index':indices[0] if indices else None,'record_id':record_id,'record_indices':indices,'source_rows':[cut['rows'][i]['source_row'] for i in indices],'paths':fields,'observed':observed,'current_source_sha256':source_hash}
  if previous is not None:ev['previous']=previous
  finding={'rule':rule,'rule_version':'1','severity':severity,'title':TITLES[rule],'evidence':ev,'explanation':explanation,'disposition':'needs_human_review'}
  finding['issue_key']=sha(canonical({'rule':rule,'namespace':cut['scope']['namespace'],'record_id':record_id,'fields':fields}))
  finding['fingerprint']=sha(canonical({'rule':rule,'version':'1','evidence':ev}));findings.append(finding)
 headers=cut['headers'];arithmetic=policy.get('line_arithmetic');aggregate=policy.get('invoice_sum');document_number=next((h for h in ['N.º documento','N.° documento'] if h in headers),None)
 if arithmetic:
  for field in [arithmetic['quantity'],arithmetic['unit_price'],arithmetic['target'],*arithmetic['deductions'],*arithmetic['additions']]:
   if field not in headers:raise ValueError('Formula field absent from source: '+field)
 if aggregate and any(k not in headers for k in [aggregate['target'],aggregate['line_field']]):raise ValueError('Aggregate formula field absent from source')
 for i,v in enumerate(values):
  key=line_key(v)
  if key is None:emit('invoice_line_identity_missing','high',[i],['ID factura','Línea'],{k:v.get(k) for k in ['ID factura','Línea']},'No se puede construir una clave de línea sin identificadores; no se imputa por posición.')
  else:keys[key].append(i)
  if not empty(v.get('ID factura')):invoices[str(v['ID factura'])].append(i)
  if v.get('Mes') not in cut['scope']['periods']:emit('invoice_period_outside_scope','medium',[i],['Mes'],v.get('Mes'),'La fila está fuera de los meses de observación declarados. No se confunde el mes de colecta con la fecha de emisión.')
  for field in ['Cantidad','Precio unitario','Descuento línea','Bonificación línea','ICE línea','Total neto']:
   if field not in headers:continue
   x=v[field]
   if empty(x):
    if field=='Total neto':emit('invoice_amount_missing','info',[i],[field],x,'Importe ausente: no se reemplaza por cero y no se incluye en una suma completa.')
   elif number(x) is None:emit('invoice_numeric_invalid','high',[i],[field],x,'El campo no contiene un número finito interpretable; revisar la extracción antes de calcular.')
   elif field in ['Cantidad','Precio unitario','Total neto'] and number(x)<=0:emit('invoice_nonpositive_measure','info',[i],[field],x,'Un valor no positivo puede ser bonificación, devolución o corrección. No se elimina ni se declara incorrecto sin el documento.')
  if arithmetic:
   fields=[arithmetic['quantity'],arithmetic['unit_price'],arithmetic['target'],*arithmetic['deductions'],*arithmetic['additions']]
   if all(number(v.get(f)) is not None for f in fields):
    coverage['line_arithmetic_eligible']+=1;expected=number(v[arithmetic['quantity']])*number(v[arithmetic['unit_price']])-sum((number(v[f]) for f in arithmetic['deductions']),decimal.Decimal(0))+sum((number(v[f]) for f in arithmetic['additions']),decimal.Decimal(0));delta=number(v[arithmetic['target']])-expected
    if abs(delta)>number(arithmetic['tolerance']):emit('invoice_line_arithmetic','medium',[i],fields,{'source':{f:v[f] for f in fields},'expected':str(expected),'difference':str(delta),'declared_formula':arithmetic},'Diferencia bajo la fórmula declarada. Confirmar unidades, impuestos y condiciones; no se ajusta el original.')
 for key,indices in keys.items():
  if len(indices)>1:emit('invoice_duplicate_line','high',indices,['ID factura','Línea'],{'key':key,'occurrences':len(indices)},'La clave es ambigua. No se escoge la primera fila ni se multiplica un cruce entre cortes.')
 business_docs=collections.defaultdict(list)
 for invoice,indices in invoices.items():
  conflicts=False
  for field in ['Distribuidor','Tipo de documento',document_number,'Fecha de emisión','Total factura','Subtotal factura','Sticker','Mes']:
   if field not in headers:continue
   known={('number',number(values[i][field])) if field in NUMERIC_FIELDS and number(values[i][field]) is not None else ('raw',canonical(values[i][field])) for i in indices if not empty(values[i][field])}
   if len(known)>1:
    conflicts=True;emit('invoice_header_conflict','high',indices,[field],[{'index':i,'value':values[i][field]} for i in indices],'Un mismo ID de factura tiene valores de cabecera incompatibles. Las celdas vacías no se convierten en un valor distinto.')
  dates=[values[i].get('Fecha de emisión') for i in indices if not empty(values[i].get('Fecha de emisión'))]
  if not dates:emit('invoice_date_missing','info',indices,['Fecha de emisión'],None,'No se puede comprobar el alcance temporal del documento.')
  elif any(date(d,cut.get('provenance',{}).get('date_system')) is None for d in dates):emit('invoice_date_invalid','medium',indices,['Fecha de emisión'],dates,'Fecha no interpretable bajo el sistema de fechas declarado; no se infiere desde el nombre del archivo.')
  representative=values[indices[0]]
  business_fields=['Sticker','Distribuidor','Tipo de documento',document_number,'Fecha de emisión']
  if not conflicts and all(not empty(representative.get(f)) for f in business_fields):business_docs[tuple(str(representative[f]).strip() for f in business_fields)].append((invoice,indices))
  if aggregate and invoice in aggregate['complete_invoices'] and not conflicts and all(line_key(values[i]) and len(keys[line_key(values[i])])==1 for i in indices):
   target=next((values[i][aggregate['target']] for i in indices if not empty(values[i][aggregate['target']])),None)
   if number(target) is not None and all(number(values[i].get(aggregate['line_field'])) is not None for i in indices):
    coverage['invoice_sum_eligible']+=1;total=sum((number(values[i][aggregate['line_field']]) for i in indices),decimal.Decimal(0));delta=number(target)-total
    if abs(delta)>number(aggregate['tolerance']):emit('invoice_sum_arithmetic','medium',indices,[aggregate['target'],aggregate['line_field']],{'header':target,'sum':str(total),'difference':str(delta),'completeness_evidence':aggregate['complete_invoices'][invoice]},'Se comparan líneas únicas y un documento declarado completo, con los campos y la tolerancia de la política.')
 for group in business_docs.values():
  if len(group)>1:emit('invoice_possible_repeat','medium',[i for _,indices in group for i in indices],business_fields,{'invoice_ids':[invoice for invoice,_ in group]},'Distintos IDs de colecta comparten los identificadores documentales exactos. Puede ser una recaptura; requiere comparar originales, sin acusar doble cobro.')
 if reference is not None:
  comparable=cut['scope']==reference['scope'];coverage['comparison_comparable']=comparable
  if not comparable:emit('invoice_scope_mismatch','info',[],['scope'],{'current':cut['scope'],'previous':reference['scope']},'No se calculan altas, bajas ni cambios por línea entre universos no equivalentes.',{'source_sha256':reference_hash})
  else:
   before=row_values(reference);prior=collections.defaultdict(list)
   for i,v in enumerate(before):
    if line_key(v):prior[line_key(v)].append(i)
   for key in sorted(set(prior)|set(keys)):
    a=prior.get(key,[]);b=keys.get(key,[]);old={'source_sha256':reference_hash,'record_indices':a,'source_rows':[reference['rows'][i]['source_row'] for i in a]}
    if len(a)>1 or len(b)>1:
     coverage['ambiguous_comparison_keys']+=1;emit('invoice_comparison_ambiguous','high',b,['ID factura','Línea'],{'key':key,'previous_count':len(a),'current_count':len(b)},'Clave duplicada en al menos un corte; se omite el cruce y no se imputa una correspondencia.',old);continue
    if not a:emit('invoice_row_added','info',b,headers,values[b[0]],'Línea incorporada al corte comparable; no se interpreta como crecimiento de ventas.',old);continue
    if not b:emit('invoice_row_removed','info',[],reference['headers'],{'key':key,'previous':before[a[0]]},'Línea ausente en el nuevo corte; no prueba desaparición de una compra.',old);continue
    coverage['matched_unique_keys']+=1
    for field in sorted(set(reference['headers'])|set(headers)):
     x=before[a[0]].get(field);y=values[b[0]].get(field)
     has_x=field in before[a[0]];has_y=field in values[b[0]]
     if canonical(x)==canonical(y) and has_x==has_y:continue
     equivalent=empty(x) and empty(y) or field in NUMERIC_FIELDS and number(x) is not None and number(y) is not None and number(x)==number(y)
     emit('invoice_format_change' if equivalent else 'invoice_value_change','info' if equivalent else 'medium',b,[field],{'key':key,'before':x,'after':y,'before_field_present':has_x,'after_field_present':has_y},'Cambio de representación sin alterar el valor interpretable.' if equivalent else 'Cambio de campo entre cortes del mismo universo. Confirmar motivo y aprobación, sin sobrescribir el corte anterior.',old)
 coverage.update(invoices=len(invoices),unique_line_keys=len(keys),duplicate_line_key_groups=sum(len(v)>1 for v in keys.values()),findings=len(findings),review_required=sum(f['severity']!='info' for f in findings),informational=sum(f['severity']=='info' for f in findings))
 return findings,coverage

TITLES={'invoice_period_outside_scope':'Fila fuera del periodo declarado','invoice_line_identity_missing':'Clave de línea incompleta','invoice_amount_missing':'Importe de línea ausente','invoice_numeric_invalid':'Medida numérica no interpretable','invoice_nonpositive_measure':'Medida no positiva por interpretar','invoice_line_arithmetic':'Diferencia con fórmula declarada de línea','invoice_duplicate_line':'Clave de línea duplicada','invoice_header_conflict':'Cabecera incompatible dentro de la factura','invoice_date_missing':'Fecha documental ausente','invoice_date_invalid':'Fecha documental no interpretable','invoice_sum_arithmetic':'Diferencia con suma documental declarada','invoice_possible_repeat':'Posible recaptura del mismo documento','invoice_scope_mismatch':'Cortes con alcance distinto','invoice_comparison_ambiguous':'Cruce omitido por clave ambigua','invoice_row_added':'Línea incorporada al nuevo corte','invoice_row_removed':'Línea ausente en el nuevo corte','invoice_format_change':'Cambio de representación entre cortes','invoice_value_change':'Campo modificado entre cortes comparables'}
