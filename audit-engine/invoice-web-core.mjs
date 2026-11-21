// Portable server evaluator. No browser state, personal scoring or automatic correction.
const VERSION='invoice-js/1.0.0';
const numericFields=new Set(['Cantidad','Precio unitario','Descuento línea','Bonificación línea','ICE línea','Total neto','Subtotal factura','Descuento factura','Bonificación factura','ICE factura','Total factura','Monto Kobo','Diferencia','Unidades','Litros','Bs por unidad']);
const empty=v=>v==null||typeof v==='string'&&!v.trim();
const assert=(v,m)=>{if(!v)throw Object.assign(Error(m),{status:400});};
function canonical(v){if(v===null||typeof v!=='object')return JSON.stringify(v);if(Array.isArray(v))return '['+v.map(canonical).join(',')+']';return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+canonical(v[k])).join(',')+'}';}
// Bounded decimal arithmetic with integers: no binary floating point tolerances.
function decimal(v){
 if(!['string','number'].includes(typeof v)||empty(v))return null;
 const text=String(v).trim();if(text.length>160)return null;
 const m=/^([+-]?)(?:(\d+)(?:\.(\d*))?|\.(\d+))(?:[eE]([+-]?\d+))?$/.exec(text);if(!m)return null;
 const fraction=m[3]??m[4]??'',exponent=Number(m[5]||0);if(Math.abs(exponent)>100)return null;
 let c=BigInt((m[1]==='-'?'-':'')+((m[2]||'0')+fraction)),s=fraction.length-exponent;
 if(s<0){c*=10n**BigInt(-s);s=0;}return {c,s};
}
function align(a,b){const s=Math.max(a.s,b.s);return [a.c*10n**BigInt(s-a.s),b.c*10n**BigInt(s-b.s),s];}
function add(a,b){const [x,y,s]=align(a,b);return {c:x+y,s};}
const negate=a=>({c:-a.c,s:a.s}),sub=(a,b)=>add(a,negate(b)),mul=(a,b)=>({c:a.c*b.c,s:a.s+b.s});
function decimalText(a){const sign=a.c<0n?'-':'',digits=(a.c<0n?-a.c:a.c).toString().padStart(a.s+1,'0');return sign+(a.s?digits.slice(0,-a.s)+'.'+digits.slice(-a.s):digits);}
function equalNumber(a,b){const x=decimal(a),y=decimal(b);return x!==null&&y!==null&&sub(x,y).c===0n;}
function exceeds(a,b){const [x,y]=align({...a,c:a.c<0n?-a.c:a.c},b);return x>y;}
function validDate(v,system){
 if(typeof v==='number'&&Number.isFinite(v)&&system==='excel_1900')return v>=1&&v<2958466&&Math.trunc(v)!==60;
 if(typeof v!=='string'||!/^\d{4}-\d{2}-\d{2}/.test(v))return false;const s=v.slice(0,10),d=new Date(s+'T00:00:00Z');return Number.isFinite(d.getTime())&&d.toISOString().slice(0,10)===s;
}
function validateCut(cut){
 assert(cut&&cut.schema==='mindtec-invoice-cut/1','Invoice cut schema required');
 assert(Array.isArray(cut.headers)&&cut.headers.length>0&&cut.headers.length<=250&&new Set(cut.headers).size===cut.headers.length&&cut.headers.every(h=>typeof h==='string'&&h.length>0&&h.length<=500),'Unique bounded source headers required');
 for(const h of ['ID factura','Línea','Mes','Sticker','Total neto'])assert(cut.headers.includes(h),'Missing source field: '+h);
 assert(!['N.º documento','N.° documento'].every(h=>cut.headers.includes(h)),'Ambiguous document-number headers');
 const scope=cut.scope;assert(scope&&['namespace','currency','period_basis','cohort_id'].every(k=>typeof scope[k]==='string'&&scope[k].trim()),'Explicit observation universe required');
 assert(Array.isArray(scope.periods)&&scope.periods.length>0&&scope.periods.every(m=>typeof m==='string'&&/^\d{4}-(0[1-9]|1[0-2])$/.test(m)),'Observation periods required');
 assert(Array.isArray(cut.rows)&&cut.rows.length>0&&cut.rows.length<=50000,'Nonempty bounded rows required');const seen=new Set();
 for(const r of cut.rows){assert(r&&Array.isArray(r.cells)&&r.cells.length===cut.headers.length&&Number.isSafeInteger(r.source_row)&&r.source_row>=2&&!seen.has(r.source_row),'Aligned unique Excel rows required');seen.add(r.source_row);assert(r.cells.every(v=>v===null||typeof v==='boolean'||typeof v==='string'&&v.length<=50000||typeof v==='number'&&Number.isFinite(v)&&(!Number.isInteger(v)||Number.isSafeInteger(v))),'Only finite scalar cells and safe numeric integers are accepted; large identifiers require strings');}
 return cut;
}
function validatePolicy(p){
 assert(p&&p.schema==='mindtec-invoice-policy/1'&&typeof p.version==='string'&&p.version.trim(),'Invoice policy version required');
 for(const name of ['line_arithmetic','invoice_sum']){const c=p[name];if(c==null)continue;assert(c&&typeof c==='object'&&!Array.isArray(c)&&typeof c.evidence==='string'&&c.evidence.trim(),'Declared formula requires evidence');const t=decimal(c.tolerance);assert(t&&t.c>=0n,'Explicit nonnegative tolerance required');
  if(name==='line_arithmetic'){assert(['quantity','unit_price','target'].every(k=>typeof c[k]==='string'&&c[k]),'Formula fields required');for(const k of ['deductions','additions'])assert(Array.isArray(c[k])&&c[k].every(v=>typeof v==='string'&&v),'Explicit formula terms required');const terms=[c.quantity,c.unit_price,c.target,...c.deductions,...c.additions];assert(new Set(terms).size===terms.length,'Formula must not double count fields');}
  else assert(['target','line_field'].every(k=>typeof c[k]==='string'&&c[k])&&c.complete_invoices&&typeof c.complete_invoices==='object'&&!Array.isArray(c.complete_invoices)&&Object.values(c.complete_invoices).every(v=>typeof v==='string'&&v.trim()),'Invoice completeness needs per-document evidence');
 }return p;
}
const rowValues=cut=>cut.rows.map(r=>Object.fromEntries(cut.headers.map((h,i)=>[h,r.cells[i]])));
function lineKey(v){if(empty(v['ID factura'])||empty(v['Línea'])||typeof v['ID factura']==='boolean'||typeof v['Línea']==='boolean')return null;return String(v['ID factura'])+'|'+String(v['Línea']);}
function group(map,key,value){if(!map.has(key))map.set(key,[]);map.get(key).push(value);}
async function evaluateInvoice(cut,policy,reference=null,sourceHash=null,referenceHash=null,hash){
 validateCut(cut);validatePolicy(policy);if(reference)validateCut(reference);assert(typeof hash==='function','SHA-256 provider required');
 const values=rowValues(cut),findings=[],keys=new Map(),invoices=new Map(),headers=cut.headers,arithmetic=policy.line_arithmetic,aggregate=policy.invoice_sum,documentNumber=['N.º documento','N.° documento'].find(h=>headers.includes(h));
 const coverage={rows:values.length,line_arithmetic_eligible:0,invoice_sum_eligible:0,line_arithmetic_configured:arithmetic!=null,invoice_sum_configured:aggregate!=null,comparison_requested:reference!==null,comparison_comparable:null,matched_unique_keys:0,ambiguous_comparison_keys:0};
 async function emit(rule,severity,indices,fields,observed,explanation,previous){
  const first=indices[0],recordId=indices.length?(lineKey(values[first])||'source-row:'+cut.rows[first].source_row):(observed&&typeof observed==='object'?String(observed.key??'cut'):'cut');
  const evidence={record_index:first??null,record_id:recordId,record_indices:indices,source_rows:indices.map(i=>cut.rows[i].source_row),paths:fields,observed,current_source_sha256:sourceHash};if(previous!==undefined)evidence.previous=previous;
  findings.push({rule,rule_version:'1',severity,title:TITLES[rule],evidence,explanation,disposition:severity==='info'?'informational':'needs_human_review',issue_key:await hash(canonical({rule,namespace:cut.scope.namespace,record_id:recordId,fields})),fingerprint:await hash(canonical({rule,version:'1',evidence}))});
 }
 if(arithmetic)for(const field of [arithmetic.quantity,arithmetic.unit_price,arithmetic.target,...arithmetic.deductions,...arithmetic.additions])assert(headers.includes(field),'Formula field absent from source: '+field);
 if(aggregate)assert([aggregate.target,aggregate.line_field].every(f=>headers.includes(f)),'Aggregate formula field absent from source');
 for(let i=0;i<values.length;i++){
  const v=values[i],key=lineKey(v);if(key===null)await emit('invoice_line_identity_missing','high',[i],['ID factura','Línea'],{'ID factura':v['ID factura']??null,'Línea':v['Línea']??null},'No se imputa una clave por posición.');else group(keys,key,i);
  if(!empty(v['ID factura']))group(invoices,String(v['ID factura']),i);
  if(!cut.scope.periods.includes(v.Mes))await emit('invoice_period_outside_scope','medium',[i],['Mes'],v.Mes,'Mes fuera del universo declarado; no se confunde colecta y emisión.');
  for(const field of ['Cantidad','Precio unitario','Descuento línea','Bonificación línea','ICE línea','Total neto']){
   if(!headers.includes(field))continue;const x=v[field],n=decimal(x);
   if(empty(x)){if(field==='Total neto')await emit('invoice_amount_missing','info',[i],[field],x,'Importe ausente: no se reemplaza por cero.');}
   else if(!n)await emit('invoice_numeric_invalid','high',[i],[field],x,'Número no interpretable bajo el contrato decimal; revisar la extracción.');
   else if(['Cantidad','Precio unitario','Total neto'].includes(field)&&n.c<=0n)await emit('invoice_nonpositive_measure','info',[i],[field],x,'Puede ser bonificación, devolución o corrección. No se declara incorrecto sin el documento.');
  }
  if(arithmetic){const fields=[arithmetic.quantity,arithmetic.unit_price,arithmetic.target,...arithmetic.deductions,...arithmetic.additions];if(fields.every(f=>decimal(v[f])!==null)){
   coverage.line_arithmetic_eligible++;let expected=mul(decimal(v[arithmetic.quantity]),decimal(v[arithmetic.unit_price]));for(const f of arithmetic.deductions)expected=sub(expected,decimal(v[f]));for(const f of arithmetic.additions)expected=add(expected,decimal(v[f]));const delta=sub(decimal(v[arithmetic.target]),expected);
   if(exceeds(delta,decimal(arithmetic.tolerance)))await emit('invoice_line_arithmetic','medium',[i],fields,{source:Object.fromEntries(fields.map(f=>[f,v[f]])),expected:decimalText(expected),difference:decimalText(delta),declared_formula:arithmetic},'Diferencia bajo la fórmula declarada. Confirmar unidades, impuestos y condiciones; no se ajusta el original.');
  }}
 }
 for(const [key,indices]of keys)if(indices.length>1)await emit('invoice_duplicate_line','high',indices,['ID factura','Línea'],{key,occurrences:indices.length},'Clave ambigua; no se escoge una fila ni se multiplica el cruce.');
 const businessDocs=new Map(),businessFields=['Sticker','Distribuidor','Tipo de documento',documentNumber,'Fecha de emisión'];
 for(const [invoice,indices]of invoices){let conflicts=false;
  for(const field of ['Distribuidor','Tipo de documento',documentNumber,'Fecha de emisión','Total factura','Subtotal factura','Sticker','Mes']){
   if(!headers.includes(field))continue;const known=[];for(const i of indices){const value=values[i][field];if(empty(value))continue;if(!known.some(x=>numericFields.has(field)&&decimal(x)!==null&&decimal(value)!==null?equalNumber(x,value):canonical(x)===canonical(value)))known.push(value);}
   if(known.length>1){conflicts=true;await emit('invoice_header_conflict','high',indices,[field],indices.map(i=>({index:i,value:values[i][field]})),'Valores de cabecera incompatibles bajo un mismo ID de factura.');}
  }
  const dates=indices.map(i=>values[i]['Fecha de emisión']).filter(v=>!empty(v));if(!dates.length)await emit('invoice_date_missing','info',indices,['Fecha de emisión'],null,'No se puede comprobar el alcance temporal del documento.');else if(dates.some(d=>!validDate(d,cut.provenance?.date_system)))await emit('invoice_date_invalid','medium',indices,['Fecha de emisión'],dates,'Fecha no interpretable bajo el sistema declarado.');
  const representative=values[indices[0]];if(!conflicts&&businessFields.every(f=>!empty(representative[f])))group(businessDocs,canonical(businessFields.map(f=>String(representative[f]).trim())),{invoice,indices});
  if(aggregate&&Object.hasOwn(aggregate.complete_invoices,invoice)&&!conflicts&&indices.every(i=>lineKey(values[i])&&keys.get(lineKey(values[i])).length===1)){
   const target=indices.map(i=>values[i][aggregate.target]).find(v=>!empty(v));if(decimal(target)!==null&&indices.every(i=>decimal(values[i][aggregate.line_field])!==null)){
    coverage.invoice_sum_eligible++;const total=indices.reduce((a,i)=>add(a,decimal(values[i][aggregate.line_field])),{c:0n,s:0}),delta=sub(decimal(target),total);
    if(exceeds(delta,decimal(aggregate.tolerance)))await emit('invoice_sum_arithmetic','medium',indices,[aggregate.target,aggregate.line_field],{header:target,sum:decimalText(total),difference:decimalText(delta),completeness_evidence:aggregate.complete_invoices[invoice]},'Suma de líneas únicas de un documento declarado completo, según la política.');
   }
  }
 }
 for(const docs of businessDocs.values())if(docs.length>1)await emit('invoice_possible_repeat','medium',docs.flatMap(x=>x.indices),businessFields,{invoice_ids:docs.map(x=>x.invoice)},'Identificadores documentales compartidos: comparar originales, sin acusar doble cobro.');
 if(reference){const comparable=canonical(cut.scope)===canonical(reference.scope);coverage.comparison_comparable=comparable;
  if(!comparable)await emit('invoice_scope_mismatch','info',[],['scope'],{current:cut.scope,previous:reference.scope},'No se calculan altas, bajas ni cambios entre universos distintos.',{source_sha256:referenceHash});
  else{const before=rowValues(reference),prior=new Map();before.forEach((v,i)=>{if(lineKey(v))group(prior,lineKey(v),i);});
   for(const key of [...new Set([...prior.keys(),...keys.keys()])].sort()){
    const a=prior.get(key)||[],b=keys.get(key)||[],old={source_sha256:referenceHash,record_indices:a,source_rows:a.map(i=>reference.rows[i].source_row)};
    if(a.length>1||b.length>1){coverage.ambiguous_comparison_keys++;await emit('invoice_comparison_ambiguous','high',b,['ID factura','Línea'],{key,previous_count:a.length,current_count:b.length},'Cruce omitido por clave duplicada en al menos un corte.',old);continue;}
    if(!a.length){await emit('invoice_row_added','info',b,headers,values[b[0]],'Línea incorporada; no se interpreta como crecimiento de ventas.',old);continue;}
    if(!b.length){await emit('invoice_row_removed','info',[],reference.headers,{key,previous:before[a[0]]},'Línea ausente; no prueba desaparición de una compra.',old);continue;}
    coverage.matched_unique_keys++;
    for(const field of [...new Set([...reference.headers,...headers])].sort()){
     const x=before[a[0]][field]??null,y=values[b[0]][field]??null,hasX=Object.hasOwn(before[a[0]],field),hasY=Object.hasOwn(values[b[0]],field);if(canonical(x)===canonical(y)&&hasX===hasY)continue;
     const equivalent=empty(x)&&empty(y)||numericFields.has(field)&&equalNumber(x,y);
     await emit(equivalent?'invoice_format_change':'invoice_value_change',equivalent?'info':'medium',b,[field],{key,before:x,after:y,before_field_present:hasX,after_field_present:hasY},equivalent?'Cambio de representación sin alterar el valor interpretable.':'Cambio de campo entre cortes del mismo universo. Confirmar motivo y aprobación, conservando el original.',old);
    }
   }
  }
 }
 Object.assign(coverage,{invoices:invoices.size,unique_line_keys:keys.size,duplicate_line_key_groups:[...keys.values()].filter(v=>v.length>1).length,findings:findings.length,review_required:findings.filter(f=>f.severity!=='info').length,informational:findings.filter(f=>f.severity==='info').length});
 return {findings,coverage,engine_version:VERSION};
}
const TITLES={"invoice_period_outside_scope":"Fila fuera del periodo declarado","invoice_line_identity_missing":"Clave de línea incompleta","invoice_amount_missing":"Importe de línea ausente","invoice_numeric_invalid":"Medida numérica no interpretable","invoice_nonpositive_measure":"Medida no positiva por interpretar","invoice_line_arithmetic":"Diferencia con fórmula declarada de línea","invoice_duplicate_line":"Clave de línea duplicada","invoice_header_conflict":"Cabecera incompatible dentro de la factura","invoice_date_missing":"Fecha documental ausente","invoice_date_invalid":"Fecha documental no interpretable","invoice_sum_arithmetic":"Diferencia con suma documental declarada","invoice_possible_repeat":"Posible recaptura del mismo documento","invoice_scope_mismatch":"Cortes con alcance distinto","invoice_comparison_ambiguous":"Cruce omitido por clave ambigua","invoice_row_added":"Línea incorporada al nuevo corte","invoice_row_removed":"Línea ausente en el nuevo corte","invoice_format_change":"Cambio de representación entre cortes","invoice_value_change":"Campo modificado entre cortes comparables"};
export {VERSION,canonical,decimal,decimalText,validateCut,validatePolicy,evaluateInvoice};
