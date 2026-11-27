"""Operational Perfect Store reconstruction with explicit uncertainty and cell lineage.

Uses a supplied historical rule/configuration, never claims the official kernel.
Unknown answers cannot become failures, successes or inapplicability by default.
"""
import base64,collections,math,re,statistics,unicodedata
from pathlib import Path
import engine,category_eligibility

VERSION='perfect-store-operational/2.2.0'
IMPLEMENTATION_BYTES=Path(__file__).read_bytes()
COMPONENTS=['Presencia','SKU núcleo','Frío','POP','Sin quiebre']

def norm(v):return re.sub(r'[^a-z0-9]','',unicodedata.normalize('NFKD',str(v or '')).encode('ascii','ignore').decode().lower())
def tokens(v):return v.split() if isinstance(v,str) else []
def count(v):
 if isinstance(v,bool) or v in (None,''):return None
 try:n=float(v)
 except (ValueError,TypeError,OverflowError):return None
 return int(n) if math.isfinite(n) and n>=0 and n.is_integer() else None
def observed(a):return a.get('state')=='observed'
def yesno(a):return a['value'] if observed(a) and a['value'] in ('si','no') else None

def evaluate(flat,catalog,policy,configuration):
 if configuration.get('schema')!='mindtec-operational-perfect-store-config/1':raise ValueError('Explicit reconstructed rule configuration required')
 if configuration.get('weights')!={name:1 for name in COMPONENTS}:raise ValueError('This operational rule supports documented equal component weights only')
 if configuration.get('cooler_rule')!='coca_cola_any_operating_vertical_others_no_coca_exclusive':raise ValueError('Explicit historical cooler access rule required')
 excluded={str(e['id']) for e in policy.get('exclusions',[])};owners=configuration['company_by_brand'];aliases=configuration.get('company_aliases',{});refs_by_key=configuration['reference_skus_by_catalog'];price_aliases=configuration.get('price_label_aliases',{})
 def company(value):return aliases.get(norm(value),norm(value))
 def owner(code,label):
  found={owners[k] for k in [norm(code),norm(label)] if k in owners}
  return next(iter(found)) if len(found)==1 else None
 stock_question_universe=configuration.get('stock_question_universe');stock_offered={}
 if stock_question_universe is not None:
  q=stock_question_universe
  if q.get('schema')!='mindtec-company-question-universe/1' or q.get('detailed_workbook_sha256')!=flat.source_sha256 or not isinstance(q.get('version'),str) or not q['version'].strip() or not isinstance(q.get('forms'),dict):raise ValueError('Source-bound stock question universe required')
  if set(q['forms'])!={r['form'] for r in flat.records if r['id'] not in excluded}:raise ValueError('Stock question universe must match admitted forms')
  known=set(aliases.values())|set(owners.values())
  for form,item in q['forms'].items():
   choices=item.get('offered_companies') if isinstance(item,dict) else None
   if not isinstance(choices,list) or not choices or any(not isinstance(v,str) or v not in known or v=='sincorrespondenciaverificada' for v in choices) or len(set(choices))!=len(choices):raise ValueError('Explicit unique stock company choices required')
   stock_offered[form]=set(choices)
  observed_forms=set()
  for observation in q.get('retained_observations',[]):
   raw=base64.b64decode(observation['content'],validate=True)
   if len(raw)>2000000 or engine.sha(raw)!=observation['original_sha256'] or observation['form'] not in stock_offered:raise ValueError('Retained stock question evidence differs')
   observed_forms.add(observation['form'])
  if observed_forms!=set(stock_offered):raise ValueError('Each stock question universe requires retained observation evidence')
 def price_label(value):return norm(price_aliases.get(value,value))
 cells={};answers={};details=[];omitted=[];eligibility_cache={};eligibility_checks=[]
 def evidence(a):
  cell_ids=[]
  for cell in a.get('cells',[]):
   key=engine.sha(engine.canonical(cell));cells[key]=cell;cell_ids.append(key)
  binding={'route':a.get('route'),'state':a['state'],'value':a.get('value'),'cell_ids':cell_ids};key=engine.sha(engine.canonical(binding));answers[key]=binding;return key
 def component(name,value,reason,sources=(),state=None,config_key=None):
  if value not in (None,0,1):raise ValueError('Binary component value required')
  return {'component':name,'state':state or ('measured' if value is not None else 'pending'),'value':value,'weight':1,'reason':reason,'evidence_ids':sorted({evidence(a) for a in sources}),'configuration_key':config_key}
 def missing(route):return {'route':route,'state':'route_not_mapped','value':None,'cells':[]}
 def na(name,reason,sources):return component(name,None,reason,sources,'not_applicable')
 prepared={}
 for record in flat.records:
  if record['id'] in excluded:continue
  r=record;coolers=flat.groups(r,'rep_enfriador');prices=flat.groups(r,'rep_precio');stock=flat.groups(r,'rep_stock_empresa')
  routes=set(flat.bindings[r['form']])|{p for ps in flat.ambiguous[r['form']].values() for p in ps}
  pops=[flat.query(r,p) for p in sorted(routes) if re.search(r'/(marcas|empresas)_material_',p)]
  prepared[r['id']]={'coolers':coolers,'prices':prices,'stock':stock,'pops':pops,'routes':routes}
 for entry in sorted(catalog,key=engine.canonical):
  cat=entry['category'];code=entry['brand_code'];brand=entry['brand'];co=owner(code,brand);config_key=engine.canonical([cat,code,brand]);reference=refs_by_key.get(config_key)
  for r in flat.records:
   if r['id'] in excluded:continue
   p=prepared[r['id']];suffix=lambda name:flat.suffix(r,name);cache_key=(r['id'],cat)
   if cache_key not in eligibility_cache:
    gate=suffix('vende_'+cat);choice=suffix('marcas_'+cat);repeats=flat.groups(r,'rep_'+cat);parent_rules=configuration.get('parent_gate_rules',{});rule_matches=[(prefix,rule) for prefix,rule in parent_rules.items() if cat.startswith(prefix)]
    if len(rule_matches)>1:raise ValueError('Parent gate rules overlap for category')
    options={};positive_sibling_answers=[]
    if rule_matches:
     prefix,rule=rule_matches[0];broad=suffix(rule['broad_suffix']);registry=suffix(rule['registry_suffix']);sibling_routes=[route for route in sorted(p['routes']) if route.split('/')[-1].startswith('vende_'+prefix)]
     positive_sibling_answers=[flat.query(r,route) for route in sibling_routes if yesno(flat.query(r,route))=='si']
     options={'parent_code':rule['parent_code'],'broad':broad,'registry':registry,'allowed_registry_codes':rule['allowed_registry_codes'],'positive_sibling':bool(positive_sibling_answers)}
    positive_repeat=any(observed(fs.get('marca_act_'+cat,missing('marca_act_'+cat))) and fs['marca_act_'+cat]['value'] not in (None,'') for fs in repeats.values())
    decision=category_eligibility.decide(gate,choice,positive_repeat=positive_repeat,**options)
    if decision['signals']:
     decision['sources']+=positive_sibling_answers+[fs['marca_act_'+cat] for fs in repeats.values() if 'marca_act_'+cat in fs and observed(fs['marca_act_'+cat])]
    support=[evidence(a) for a in decision['sources']]
    eligibility_cache[cache_key]={'gate':gate,'choice':choice,'repeats':repeats,'decision':decision,'support':support}
    eligibility_checks.append({'kobo_id':r['id'],'month':r['month'],'category':cat,'eligible':decision['eligible'],'method':decision['method'],'reason':decision['reason'],'parent_code':decision['parent_code'],'signals':decision['signals'],'support':support})
   ec=eligibility_cache[cache_key];gate=ec['gate'];choice=ec['choice'];repeats=ec['repeats'];decision=ec['decision'];matching=[fs for fs in repeats.values() if observed(fs.get('marca_act_'+cat,missing('marca_act_'+cat))) and fs['marca_act_'+cat]['value']==code]
   repeat_evidence=[a for fs in matching for f,a in fs.items() if f in ('marca_act_'+cat,'marca_lbl_'+cat)]
   explicit_presence=(code in tokens(choice['value'])) if observed(choice) else None
   has=True if matching else explicit_presence
   conflicting=bool(matching) and explicit_presence is False
   eligible=decision['eligible']
   if eligible is False:
    omitted.append({'id':r['id'],'month':r['month'],'category':cat,'brand_code':code,'reason':decision['reason'],'eligibility_method':decision['method'],'eligibility_evidence':evidence(gate),'eligibility_support':ec['support']});continue
   presence=int(has) if eligible is True and has is not None and not conflicting else None
   cs=[component('Presencia',presence,'Declaración de marca en una subcategoría elegible; contradicciones o respuestas ausentes quedan pendientes.',decision['sources']+repeat_evidence)]
   # This is the documented historic price-basket proxy, not a certified core-SKU matrix.
   selected=[fs['sku_precio_label'] for fs in p['prices'].values() if 'sku_precio_label' in fs];nprices=suffix('n_skus_precio');price_choice=suffix('skus_precio_catalogo')
   selected_good=[a for a in selected if observed(a) and isinstance(a['value'],str)];selected_count=count(nprices.get('value')) if observed(nprices) else len(tokens(price_choice['value'])) if observed(price_choice) else None
   if not co or reference is None:cs.append(component('SKU núcleo',None,'Falta homologación o canasta explícita de esta marca en la configuración histórica.',config_key=config_key))
   elif not reference:cs.append(na('SKU núcleo','La canasta histórica explícita no exige referencias a esta marca.',[]))
   else:
    match=any(price_label(a['value']) in {price_label(s) for s in reference} for a in selected_good)
    complete=selected_count is not None and selected_count==len(selected_good) and len(selected_good)==len(selected)
    val=1 if match else 0 if complete else None
    cs.append(component('SKU núcleo',val,'Proxy histórico: al menos una referencia configurada en la canasta de precios. No certifica matriz núcleo ni versión oficial.',selected+[nprices,price_choice],config_key=config_key))
   cooler_gate=suffix('hay_enfriadores');cooler_count=suffix('cuantos_enfriadores_bsa')
   # The earlier form repeats every cooler and has no BSA-specific count.
   # Use its explicit total only when that specific route is absent from schema,
   # never to fill an empty BSA count in the later form.
   if cooler_count['state']=='route_not_mapped':cooler_count=suffix('cuantos_enfriadores')
   expected=count(cooler_count.get('value')) if observed(cooler_count) else None;access=[];unknown=[];cooler_sources=[cooler_gate,cooler_count]
   for key,fs in p['coolers'].items():
    cooler_sources+=list(fs.values());typ=fs.get('tipo_enfriador',missing('tipo_enfriador'));on=fs.get('enfriador_encendido',missing('enfriador_encendido'));sponsor=fs.get('enfriador_patrocinado',missing('enfriador_patrocinado'));sponsor_brand=fs.get('marca_enfriador',missing('marca_enfriador'))
    typval=norm(typ['value']) if observed(typ) else None
    if typval and typval not in ('neveravertical','enfriadorvertical','neveracasera'):continue
    if not typval or (norm(code)!='cocacola' and (yesno(sponsor) is None or yesno(sponsor)=='si' and not observed(sponsor_brand))):unknown.append(key);continue
    blocked=norm(code)!='cocacola' and yesno(sponsor)=='si' and norm(sponsor_brand['value'])=='cocacola'
    if not blocked and yesno(on)=='si':access.append(key)
    elif not blocked and yesno(on) is None:unknown.append(key)
   cooler_complete=expected is not None and expected==len(p['coolers'])
   if yesno(cooler_gate)=='no' and p['coolers']:unknown.append('contradictory_cooler_gate')
   if access and 'contradictory_cooler_gate' not in unknown:
    cold_groups=flat.groups(r,'rep_frio_'+cat);enumeration=suffix('n_frio_'+cat);code_field='marca_frio_act_'+cat;face_field='caras_frio_'+cat
    if not cold_groups:
     cold_groups=flat.groups(r,'rep_caras_frias');enumeration=suffix('n_marcas_frias');code_field='marca_fria_actual';face_field='caras_frias'
    cold_sources=[];cold_values=[];unresolved_cold=False
    for fs in cold_groups.values():
     ca=fs.get(code_field,missing(code_field))
     if not observed(ca):unresolved_cold=True
     if observed(ca) and ca['value']==code:
      fa=fs.get(face_field,missing(face_field));cold_sources += [ca,fa];cold_values.append(count(fa['value']) if observed(fa) else None)
    ncold=count(enumeration['value']) if observed(enumeration) else None
    complete=ncold is not None and ncold==len(cold_groups) and not unresolved_cold
    val=1 if any(v is not None and v>0 for v in cold_values) else None if any(v is None for v in cold_values) or len(cold_values)>1 else 0 if complete else None
    cs.append(component('Frío',val,'Acceso según regla histórica reconstruida y caras frías declaradas. Sin vínculo cara-equipo; enumeración incompleta queda pendiente.',cooler_sources+cold_sources+[enumeration]))
   elif unknown or yesno(cooler_gate) not in ('si','no') or (not cooler_complete and yesno(cooler_gate)!='no'):
    cs.append(component('Frío',None,'No se puede resolver acceso o completitud de equipos; no se declara no aplica por falta de filas.',cooler_sources))
   else:cs.append(na('Frío','No hay equipo operativo accesible según la regla histórica documentada.',cooler_sources))
   pop_gate=suffix('tiene_material_marketing');pop_sources=[pop_gate]+p['pops'];filled=[a for a in p['pops'] if observed(a)];pcodes=[t for a in filled for t in tokens(a['value'])];known_companies=set(owners.values());popowners={owners.get(norm(t)) or company(t) for t in pcodes};unresolved_owner=any(v not in known_companies for v in popowners)
   if not co:cs.append(component('POP',None,'Propietario de marca no homologado.',pop_sources))
   elif yesno(pop_gate)=='no' and pcodes:cs.append(component('POP',None,'Se declara ausencia de POP pero hay marcas/empresas enumeradas.',pop_sources))
   elif yesno(pop_gate)=='no':cs.append(component('POP',0,'La tienda declara no tener material de marketing.',pop_sources))
   elif co in popowners:cs.append(component('POP',1,'Material declarado de alguna marca de la empresa propietaria, según homologación histórica.',pop_sources))
   elif filled and not unresolved_owner and yesno(pop_gate)=='si':cs.append(component('POP',0,'Listas POP observadas y homologadas no incluyen al propietario.',pop_sources))
   else:cs.append(component('POP',None,'Lista POP vacía, sin homologar o no resuelta; no equivale a ausencia.',pop_sources))
   stock_rows=[]
   for fs in p['stock'].values():
    c=fs.get('empresa_actual_stock',missing('empresa_actual_stock'))
    if observed(c) and company(c['value'])==co:stock_rows.append(fs)
   buys=suffix('empresas_compra');stock_sources=[buys]+[a for fs in stock_rows for a in fs.values()]
   stock_value=yesno(stock_rows[0].get('hay_quiebre_empresa',missing('hay_quiebre_empresa'))) if len(stock_rows)==1 else None
   if stock_value=='no' and any(cell['value'] not in (None,'') for key,a in stock_rows[0].items() if key in ('marca_quiebre','motivo_quiebre','tiempo_agotado') for cell in a.get('cells',[])):stock_value=None
   offered=stock_offered.get(r['form']);ncompanies=suffix('n_empresas_compra');stock_sources.append(ncompanies)
   declared=[company(t) for t in tokens(buys['value'])] if observed(buys) and isinstance(buys['value'],str) else [] if ncompanies.get('state')=='observed' and ncompanies.get('value')==0 and buys['state']=='empty_observation' else None
   ids=[fs.get('empresa_actual_stock',missing('empresa_actual_stock')) for fs in p['stock'].values()];stock_sources+=ids
   codes=[company(a['value']) for a in ids if observed(a) and isinstance(a['value'],str)];expected=count(ncompanies['value']) if observed(ncompanies) and type(ncompanies['value']) in (int,float) else None
   indices=[int(re.fullmatch(r'rep_stock_empresa\[([1-9]\d*)\]',key)[1]) for key in p['stock']]
   scope_complete=offered is not None and declared is not None and expected is not None and expected==len(declared)==len(set(declared))==len(p['stock'])==len(codes)==len(set(codes)) and set(codes)==set(declared) and set(declared)<=offered and set(indices)==set(range(1,expected+1))
   if co and stock_value is not None and declared is not None and co in declared and (offered is None or co in offered):cs.append(component('Sin quiebre',int(stock_value=='no'),'Declaración explícita de quiebre por empresa compradora; no inventario de SKU.',stock_sources))
   elif co and scope_complete and co in offered and co not in declared:cs.append(na('Sin quiebre','La empresa se ofrecía en el formulario y la enumeración completa de compradores no la incluye.',stock_sources))
   else:cs.append(component('Sin quiebre',None,'La empresa no se ofrecía en la pregunta, falta su universo admitido o no se resuelve la declaración de forma única. No preguntado no equivale a no comprador.',stock_sources))
   cs[-1]['configuration_key']='stock_question_universe/'+r['form'] if stock_question_universe else None
   known=[c for c in cs if c['state']=='measured'];pending=[c for c in cs if c['state']=='pending'];n=sum(c['value'] for c in known);den=len(known);miss=len(pending);score=100*n/den if den and not miss and eligible is True else None
   details.append({'month':r['month'],'year':r['month'][:4],'kobo_id':r['id'],'category':cat,'brand_code':code,'brand':brand,'company':co,'eligible':eligible,'eligibility_evidence':evidence(gate),'eligibility_support':ec['support'],'eligibility_method':decision['method'],'components':cs,'numerator':n,'measured_denominator':den,'pending_components':miss,'score':score,'conditional_minimum':100*n/(den+miss) if den+miss else None,'conditional_maximum':100*(n+miss)/(den+miss) if den+miss else None,'rule_version':VERSION})
 def summarize(rows,period,kind):
  values=[r['score'] for r in rows if r['score'] is not None];unknown=sum(r['eligible'] is None for r in rows);complete=len(values)==len(rows) and not unknown
  return {'period':period,'period_kind':kind,'category':rows[0]['category'],'brand_code':rows[0]['brand_code'],'brand':rows[0]['brand'],'company':rows[0]['company'],'store_month_observations':len(rows),'unique_visits':len({r['kobo_id'] for r in rows}),'eligibility_pending':unknown,'complete_store_scores':len(values),'score':statistics.mean(values) if complete and values else None,'partial_mean_not_population_score':statistics.mean(values) if values else None,'minimum':statistics.mean(r['conditional_minimum'] for r in rows) if rows and not unknown else None,'maximum':statistics.mean(r['conditional_maximum'] for r in rows) if rows and not unknown else None,'months_observed':sorted({r['month'] for r in rows}),'components':{name:{'fulfilled':sum(c['value']==1 and c['state']=='measured' for r in rows for c in r['components'] if c['component']==name),'measured':sum(c['state']=='measured' for r in rows for c in r['components'] if c['component']==name),'pending':sum(c['state']=='pending' for r in rows for c in r['components'] if c['component']==name),'not_applicable':sum(c['state']=='not_applicable' for r in rows for c in r['components'] if c['component']==name)} for name in COMPONENTS}}
 monthly=collections.defaultdict(list);annual=collections.defaultdict(list)
 for d in details:
  monthly[(d['month'],d['category'],d['brand_code'],d['brand'])].append(d);annual[(d['year'],d['category'],d['brand_code'],d['brand'])].append(d)
 return {'schema':'mindtec-operational-perfect-store/2','version':VERSION,'source_sha256':flat.source_sha256,'configuration_version':configuration['version'],'stock_question_universe_version':stock_question_universe['version'] if stock_question_universe else None,'details':details,'monthly':[summarize(rows,k[0],'month') for k,rows in sorted(monthly.items())],'annual_observed_months':[summarize(rows,k[0],'year_observed_months_only') for k,rows in sorted(annual.items())],'explicitly_ineligible':omitted,'eligibility_checks':eligibility_checks,'cells':cells,'answer_evidence':answers,'mapping_coverage':flat.coverage(),'limits':['Operational reconstruction using historical documented configuration; not the official MindTEC calculation kernel or certified period version.','Core-SKU component uses a historical price-basket proxy, not a certified core assortment matrix.','Missing answers, incomplete repetitions and unresolved mappings remain pending.','Year view covers observed months only, averaged over store-month observations; not a complete calendar year.','No panel comparison is asserted without compatible source, scope and rule versions.','A signal or reconstruction difference does not establish fraud.']}
