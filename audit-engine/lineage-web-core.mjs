// Server-side dependency matching; a link never asserts numeric KPI impact.
const LINEAGE_VERSION='lineage-js/1.0.0';
function lineageAssert(v,message){if(!v)throw Object.assign(Error(message),{status:400});}
function lineageCanonical(v){if(v===null||typeof v!=='object')return JSON.stringify(v);if(Array.isArray(v))return '['+v.map(lineageCanonical).join(',')+']';return '{'+Object.keys(v).sort().map(k=>JSON.stringify(k)+':'+lineageCanonical(v[k])).join(',')+'}';}
function lineageGroup(map,key,v){if(!map.has(key))map.set(key,[]);map.get(key).push(v);}
function dependencyContract(b){
 lineageAssert(b?.schema==='mindtec-lineage-dependencies/1','Dependency bundle schema required');
 lineageAssert(typeof b.projection_scope==='string'&&b.projection_scope.length<=2000&&['kpis','kpi_scope','perfect_store_details','perfect_store_manifest'].every(role=>typeof b.parent_files?.[role]?.filename==='string'&&b.parent_files[role].filename.length<=500&&/^[a-f0-9]{64}$/.test(b.parent_files[role].sha256)),'Parent artifact identities and projection scope required');
 lineageAssert(Array.isArray(b.kpis)&&b.kpis.length>0&&b.kpis.length<=10000,'Bounded nonempty KPI rows required');
 lineageAssert(Array.isArray(b.perfect_store)&&b.perfect_store.length<=20000,'Bounded Perfect Store rows required');
 lineageAssert(Array.isArray(b.invoice_ref_sets)&&b.invoice_ref_sets.length<=10000&&b.invoice_ref_sets.every(a=>Array.isArray(a)&&a.length<=100000&&a.every(k=>typeof k==='string'&&k.length<=1000)),'Invalid invoice dependency sets');
 lineageAssert(Array.isArray(b.answer_pool)&&b.answer_pool.length<=100000,'Invalid answer pool');
 for(const a of b.answer_pool)lineageAssert(a&&typeof a.ruta==='string'&&a.ruta.length<=2000&&Object.hasOwn(a,'valor'),'Original answer reference required');
 const ids=new Set();for(const k of b.kpis){lineageAssert(['id','mes','marca','categoria','indicador'].every(key=>typeof k[key]==='string'&&k[key].length>0)&&Number.isSafeInteger(k.invoice_ref_set)&&k.invoice_ref_set>=0&&k.invoice_ref_set<b.invoice_ref_sets.length&&!ids.has(k.id),'Unique KPI and valid dependency set required');ids.add(k.id);}
 let refs=0;const detailKeys=new Set();for(const r of b.perfect_store){lineageAssert(['mes','categoria','marca'].every(key=>typeof r[key]==='string')&&['string','number'].includes(typeof r.id_envio)&&Array.isArray(r.components)&&r.components.length<=30,'Invalid Perfect Store dependency row');const key=lineageCanonical([r.mes,r.categoria,r.marca,String(r.id_envio)]);lineageAssert(!detailKeys.has(key),'Duplicate Perfect Store dependency row');detailKeys.add(key);for(const c of r.components){lineageAssert(typeof c.name==='string'&&typeof c.state==='string'&&Array.isArray(c.answer_refs)&&c.answer_refs.every(i=>Number.isSafeInteger(i)&&i>=0&&i<b.answer_pool.length),'Invalid component source reference');refs+=c.answer_refs.length;}}
 lineageAssert(refs<=1000000,'Too many component references');return b;
}
function invoiceDependencyLinks(b,cut,findings,sourceHash){
 lineageAssert(typeof b.kpi_scope?.sha256_facturas==='string'&&b.kpi_scope.sha256_facturas===cut.provenance?.original_sha256,'KPI invoice workbook differs from the audited original');
 const keys=new Map(),byRow=new Map(),byKey=new Map(),idColumn=cut.headers.indexOf('ID factura'),lineColumn=cut.headers.indexOf('Línea');
 lineageAssert(idColumn>=0&&lineColumn>=0,'Invoice identity columns required');
 for(const row of cut.rows){const id=row.cells[idColumn],line=row.cells[lineColumn],key=id==null||line==null||typeof id==='boolean'||typeof line==='boolean'||typeof id==='string'&&!id.trim()||typeof line==='string'&&!line.trim()?null:String(id)+'|'+String(line);byRow.set(row.source_row,key);if(key)keys.set(key,(keys.get(key)||0)+1);}
 for(const f of findings){const e=f.evidence;lineageAssert(e.current_source_sha256===sourceHash,'Invoice finding cut mismatch');lineageAssert((e.source_rows||[]).every(r=>byRow.has(r)),'Finding points to an absent current row');for(const key of new Set((e.source_rows||[]).map(r=>byRow.get(r)).filter(Boolean)))lineageGroup(byKey,key,f);}
 return b.kpis.map(k=>{const dependencies=[...new Set(b.invoice_ref_sets[k.invoice_ref_set])],links=dependencies.flatMap(key=>(byKey.get(key)||[]).map(f=>({kind:'declared_invoice_input',line_key:key,key_occurrences:keys.get(key),finding_fingerprint:f.fingerprint,rule:f.rule,severity:f.severity,paths:f.evidence.paths,numeric_impact:'not_established'})));return {kpi_id:k.id,month:k.mes,brand:k.marca,category:k.categoria,indicator:k.indicador,published:k.publicado_original??null,operational_value:k.operational_value??null,declared_dependencies:dependencies.length,missing_dependencies:dependencies.filter(k=>!keys.has(k)),ambiguous_dependencies:dependencies.filter(k=>keys.get(k)>1),links,status:links.length?'declared_inputs_with_signals':dependencies.length?'no_signals_in_declared_invoice_inputs':'no_declared_invoice_dependency',numeric_impact:'not_established'};});
}
function perfectStoreDependencyLinks(b,scan,scanHash,findings){
 const source=b.perfect_store_manifest?.fuentes?.find(s=>s.archivo==='cuestionarios_normalizados_2026-11-13.json');lineageAssert(source&&source.sha256===scanHash,'Perfect Store and Scan cuts differ');
 const records=new Map(),signals=new Map();for(let i=0;i<scan.envios.length;i++){const r=scan.envios[i],answers=new Map();for(const a of r.respuestas)lineageGroup(answers,a.ruta,a.valor);lineageGroup(records,String(r.envioKobo),{index:i,answers});}
 for(const f of findings){lineageAssert(Number.isSafeInteger(f.evidence.record_index)&&f.evidence.record_index>=0&&f.evidence.record_index<scan.envios.length,'Invalid Scan finding record');lineageGroup(signals,f.evidence.record_index,f);}
 return b.perfect_store.map((row,position)=>{const candidates=records.get(String(row.id_envio))||[],record=candidates.length===1?candidates[0]:null,recordSignals=record?signals.get(record.index)||[]:[];
  const components=row.components.map(c=>{const verified=new Set(),unresolved=new Set(),linked=new Map();for(const ref of c.answer_refs){const s=b.answer_pool[ref],answers=record?.answers.get(s.ruta)||[];if(answers.length!==1||lineageCanonical(answers[0])!==lineageCanonical(s.valor))unresolved.add(s.ruta);else {verified.add(s.ruta);for(const f of recordSignals)if(f.evidence.paths.includes(s.ruta))linked.set(f.fingerprint,f);}}
   const links=[...linked.values()].map(f=>({kind:'component_source_overlap',finding_fingerprint:f.fingerprint,rule:f.rule,severity:f.severity,record_index:record.index,matched_paths:[...verified].filter(p=>f.evidence.paths.includes(p)).sort(),numeric_impact:'not_established'}));
   return {component:c.name,state:c.state,value:c.value??null,weight:c.weight,verified_paths:[...verified].sort(),unresolved_paths:[...unresolved].sort(),links};
  });return {detail_index:position,month:row.mes,category:row.categoria,brand:row.marca,company:row.empresa??null,record_id:String(row.id_envio),record_matches:candidates.length,components};
 });
}
function evaluateLineage(bundle,invoice,scan){
 dependencyContract(bundle);const invoice_kpis=invoiceDependencyLinks(bundle,invoice.source,invoice.findings,invoice.source_sha256),perfect_store=perfectStoreDependencyLinks(bundle,scan.source,scan.source_sha256,scan.findings);
 const summary={kpi_rows:invoice_kpis.length,indicators:new Set(invoice_kpis.map(r=>r.indicator)).size,kpi_rows_with_links:invoice_kpis.filter(r=>r.links.length).length,invoice_links:invoice_kpis.reduce((n,r)=>n+r.links.length,0),missing_invoice_dependencies:invoice_kpis.reduce((n,r)=>n+r.missing_dependencies.length,0),perfect_store_rows:perfect_store.length,perfect_store_links:perfect_store.reduce((n,r)=>n+r.components.reduce((m,c)=>m+c.links.length,0),0),unresolved_component_paths:perfect_store.reduce((n,r)=>n+r.components.reduce((m,c)=>m+c.unresolved_paths.length,0),0)};
 return {engine_version:LINEAGE_VERSION,invoice_kpis,perfect_store,summary,parent_bytes_verified_on_server:false,numeric_impact:'not_established'};
}
export {LINEAGE_VERSION,dependencyContract,invoiceDependencyLinks,perfectStoreDependencyLinks,evaluateLineage};
