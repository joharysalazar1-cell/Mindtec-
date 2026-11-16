"""Read wide Scan XLSX answers through exact, explicitly scoped historical labels.

This is not the official JSON API contract. Historical values are never used.
Ambiguous header-to-route bindings remain unresolved, including empty aliases.
"""
import collections,re
from pathlib import Path
import engine,collection_audit

VERSION='wide-scan-answers/1.0.1'
IMPLEMENTATION_BYTES=Path(__file__).read_bytes()
METADATA=['Envio Kobo','Formulario','Fecha visita','Enviado','Encuestador','Codigo Tienda','Latitud','Longitud','Estado envio','Revision','Corregido','Tienda (maestro)','Tendero (maestro)','Zona (maestro)','Canal (maestro)']

class FlatAnswers:
 def __init__(self,workbook_cut,historical):
  if workbook_cut.get('schema')!='mindtec-collection-result-cut/1':raise ValueError('Typed workbook cut required')
  matches=[t for t in workbook_cut['tables'] if t['sheet']=='Envíos']
  if len(matches)!=1:raise ValueError('One detailed Envíos sheet required')
  self.table=matches[0];self.provenance=workbook_cut['provenance'];self.source_sha256=self.provenance['original_sha256']
  if self.table.get('formula_cells_using_cached_values'):raise ValueError('Cached formulas cannot become original answers')
  self.headers=self.table['headers'];self.columns={h:i for i,h in enumerate(self.headers)}
  if any(h not in self.columns for h in METADATA):raise ValueError('Detailed export metadata incomplete')
  engine.validate_scan(historical)
  schemas=collections.defaultdict(lambda:collections.defaultdict(set))
  for e in historical['envios']:
   if not isinstance(e.get('formulario'),str):raise ValueError('Exact historical form identity required')
   for answer in e['respuestas']:
    route=answer['ruta'];question=answer.get('pregunta')
    if not isinstance(question,str) or not question:continue
    base=question+''.join(re.findall(r'\[\d+\]',route))
    schemas[e['formulario']][base].add(route)
    schemas[e['formulario']][base+' ('+route+')'].add(route)
  self.bindings={};self.ambiguous={};self.unmapped={}
  for form,labels in schemas.items():
   routes=collections.defaultdict(list);ambiguous={};unmapped=[]
   for h in self.headers:
    if h in METADATA:continue
    candidates=labels.get(h,set())
    if len(candidates)==1:routes[next(iter(candidates))].append(self.columns[h])
    elif candidates:ambiguous[h]=sorted(candidates)
    else:unmapped.append(h)
   self.bindings[form]=dict(routes);self.ambiguous[form]=ambiguous;self.unmapped[form]=unmapped
  self.records=[];identities=set()
  for row in self.table['rows']:
   meta={h:row['cells'][self.columns[h]] for h in METADATA};eid=collection_audit.identifier(meta['Envio Kobo']);form=meta['Formulario'];date=meta['Fecha visita']
   if not eid or eid in identities:raise ValueError('Detailed Kobo IDs must be complete and unique')
   if form not in self.bindings:raise ValueError('Form has no exact historical question schema')
   if not isinstance(date,str) or not re.fullmatch(r'\d{4}-(?:0[1-9]|1[0-2])-\d{2}',date):raise ValueError('Explicit YYYY-MM-DD visit date required')
   identities.add(eid);self.records.append({'id':eid,'form':form,'month':date[:7],'metadata':meta,'row':row,'cache':{}})
 def cell(self,record,index):
  row=record['row'];letters=''.join(c for c in self.table['header_coordinates'][index] if c.isalpha())
  return {'source_sha256':self.source_sha256,'sheet':self.table['sheet'],'source_row':row['source_row'],'coordinate':row['coordinates'][index] or letters+str(row['source_row']),'column':self.headers[index],'value':row['cells'][index],'kobo_id':record['id']}
 def query(self,record,route):
  if route in record['cache']:return record['cache'][route]
  columns=self.bindings[record['form']].get(route,[]);refs=[self.cell(record,i) for i in columns];filled=[r['value'] for r in refs if r['value'] not in (None,'')]
  values={engine.canonical(v) for v in filled};ambiguous=[h for h,rs in self.ambiguous[record['form']].items() if route in rs]
  # An ambiguous unsuffixed header may carry a second answer for this route;
  # do not silently discard it even if an explicit-path alias also exists.
  if ambiguous:
   refs += [self.cell(record,self.columns[h]) for h in ambiguous]
   state='ambiguous_header_binding';value=None
  elif len(values)>1:state='conflicting_cells_for_route';value=None
  elif filled:state='observed';value=filled[0]
  elif columns:state='empty_observation';value=None
  else:state='route_not_mapped';value=None
  answer={'route':route,'state':state,'value':value,'cells':refs}
  record['cache'][route]=answer;return answer
 def suffix(self,record,suffix):
  routes=set(r for r in self.bindings[record['form']] if r.endswith('/'+suffix))
  routes.update(r for rs in self.ambiguous[record['form']].values() for r in rs if r.endswith('/'+suffix))
  if len(routes)==1:return self.query(record,next(iter(routes)))
  return {'route':None,'state':'suffix_ambiguous' if routes else 'route_not_mapped','value':None,'cells':[c for r in sorted(routes) for c in self.query(record,r)['cells']]}
 def groups(self,record,prefix):
  groups=collections.defaultdict(dict);active=set()
  routes=set(self.bindings[record['form']])|{r for rs in self.ambiguous[record['form']].values() for r in rs}
  for route in sorted(routes):
   if not route.startswith(prefix+'[') or '/' not in route:continue
   group,field=route.split('/',1);a=self.query(record,route)
   groups[group][field]=a
   if a['state']=='observed' or any(c['value'] not in (None,'') for c in a['cells']):active.add(group)
  return {g:fields for g,fields in groups.items() if g in active}
 def coverage(self):
  return {'schema':'mindtec-wide-answer-mapping-coverage/1','version':VERSION,'method':'Exact question text and repeat indices within exact form identity; historical values not reused.','workbook_sha256':self.source_sha256,'records':len(self.records),'months':dict(collections.Counter(r['month'] for r in self.records)),'forms':{form:{'mapped_routes':len(self.bindings[form]),'mapped_columns':sum(map(len,self.bindings[form].values())),'ambiguous_headers':self.ambiguous[form],'unmapped_headers':self.unmapped[form]} for form in self.bindings},'not_official_api_route_export':True}
