"""Explicit operational reconstructions for the remaining KPI scopes.

Uses current Scan product identities, retained invoice windows, and captured
v329 formulas. Scenarios are not certified replicas of unknown configuration.
"""
import collections,datetime as dt,json,math,sqlite3,statistics,hashlib
from pathlib import Path
import scan_product_reference
ROOT=Path(__file__).resolve().parent
BASE=ROOT/'private/platform-recovered-2026-11-23'
def J(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False)
def fold(v):return scan_product_reference.key(v)
CAT={'Agua sin gas':'bsa_agua','Agua con gas':'bsa_agua_con_gas','Agua funcional':'bsa_agua_funcional','Agua saborizada':'bsa_agua_saborizada','Energizantes':'bsa_energizantes','Gaseosas o bebidas carbonatadas':'bsa_gaseosas','Gaseosas':'bsa_gaseosas','Gaseosas sin azúcar':'bsa_gaseosas_sin_azucar','Bebidas hidratantes o isotónicas':'bsa_hidratantes','Jugos':'bsa_jugos','Bebida láctea (ej. Pilfrut, Karpil, Biofrut, Power Frutt)':'lac_bebida_lactea','Bebida láctea':'lac_bebida_lactea','Leche deslactosada':'lac_leche_deslactosada','Leche natural':'lac_leche_natural','Leche saborizada':'lac_leche_saborizada','Leche de soya':'lac_leche_soya'}
def date(v):return dt.datetime(1899,12,30)+dt.timedelta(days=v) if type(v) in (int,float) and v>=61 else None
def column(index):
 result='';index+=1
 while index:index,part=divmod(index-1,26);result=chr(65+part)+result
 return result

def build():
 p=json.loads((BASE/'soc24u/integrated-result.json').read_text(encoding='utf8'))
 ref=scan_product_reference.Reference(BASE/'skus_catalogo_2026-11-24.csv',BASE/'skus_resueltos_2026-11-24.csv',BASE/'skus_censo_resueltos_2026-11-24.csv',p['configuration']['price_label_aliases'])
 db=sqlite3.connect(ROOT/'private/cs24ready/base_analitica.sqlite');db.row_factory=sqlite3.Row
 visit_rows=list(db.execute('SELECT * FROM visits'));visit_keys={(v['sticker'],v['month']):v['kobo_id'] for v in visit_rows}
 assert len(visit_keys)==108
 invoice=json.loads((BASE/'invoice-cut-retained.json').read_text(encoding='utf8'));purchases=[];invoice_status=collections.Counter();invoice_evidence={}
 for row in invoice['rows']:
  v=dict(zip(invoice['headers'],row['cells']));vid=visit_keys.get((str(v['Sticker']),v['Mes']))
  match=ref.resolve(code=v.get('Código Kobo SKU'),label=v.get('SKU (maestro)'),selected=v.get('Texto leído'));product=match.get('product',{});cat=CAT.get(product.get('Subcategoría'));when=date(v.get('Fecha de emisión'));visit_date=date(v.get('Fecha de visita'));net=v.get('Total neto')
  if not vid or not cat or when is None or visit_date is None or type(net) not in (int,float) or net<0:
   invoice_status['outside_computable_documented_window']+=1;continue
  days=(visit_date-when).total_seconds()/86400
  purchases.append({'source_row':row['source_row'],'invoice_id':v['ID factura'],'line':v['Línea'],'kobo_id':vid,'month':v['Mes'],'category':cat,'brand':product['Marca'],'net':net,'days_before_visit':days,'reference':match})
  fields=['ID factura','Línea','Sticker','Mes','Fecha de emisión','Fecha de visita','Total neto','Código Kobo SKU','SKU (maestro)']
  invoice_evidence[str(row['source_row'])]={'sheet':'Ítems de facturas','source_row':row['source_row'],'invoice_id':v['ID factura'],'line':v['Línea'],'kobo_id':vid,'month':v['Mes'],'canonical_brand':product['Marca'],'canonical_product':product['Valor del catálogo'],'master_csv_line':product['source_line'],'match_basis':match['basis'],'net':net,'days_before_visit':days,'original_cells':[{'coordinate':column(invoice['headers'].index(f))+str(row['source_row']),'field':f,'value':v[f]} for f in fields]}
  invoice_status['matched_invoice_rows']+=1
 price_rows=[]
 for r in db.execute("SELECT r.*,o.kobo_id,o.month,o.payload AS observation FROM resolved_products r JOIN observations o ON o.entity=r.entity AND o.source_row=r.source_row WHERE r.entity='prices' AND r.status='matched'"):
  o=json.loads(r['observation']);value=o.get('Precio Bs');volume=r['content'];unit=fold(r['unit']);litres=volume/1000 if unit=='ml' and volume else volume if unit in ('l','litro','litros') else None;category=CAT.get(r['canonical_category'])
  if category and litres and litres>0 and type(value) in (int,float) and value>0:
   price_rows.append({'source_row':r['source_row'],'kobo_id':r['kobo_id'],'month':r['month'],'category':category,'brand':r['canonical_brand'],'sku':r['canonical_label'],'litres':litres,'location':o['Dónde'],'bs_per_litre':value/litres,'price_bs':value,'reference':json.loads(r['reference_payload'])})
 photo_products=ROOT.parent.parent/'mindtec-web/app-site/source/product-evidence-2026-11-24/result.json'
 photo_excluded_prices=set()
 if photo_products.exists():photo_excluded_prices={r['source_row'] for r in json.loads(photo_products.read_text(encoding='utf8')).get('excluded_photo_links',[]) if r['entity']=='prices'}
 price_rows=[r for r in price_rows if r['source_row'] not in photo_excluded_prices]
 results=[]
 def add(s,metric,value=None,state='pending_inputs',**extra):
  c=p['catalogue'][s['c']];results.append({'period':s['period'],'kind':s['kind'],'category':p['categories'][c['category']],'brand':c['brand'],'brand_code':c['brand_code'],'metric':metric,'value':value,'state':state,**extra})
 # Source store denominators and evidence remain those of the reviewed projection.
 for s in p['series']:
  c=p['catalogue'][s['c']];cat=p['categories'][c['category']];months=[s['period']] if s['kind']=='month' else ['2026-09','2026-10'];rows=[p['stores'][i] for i in s['stores']]
  core=[];supports=[]
  for row in rows:
   if row['ps'] is None:continue
   detail=p['ps_details'][row['ps']]
   for component in detail['components']:
    if component['name']=='SKU núcleo' and component['state']!='not_applicable':core.append(component);supports.append({'visit':p['visits'][row['v']],'evidence_set':component['evidence_set'],'configuration_key':component['configuration_key']})
  known=[x['value'] for x in core if x['state']=='measured'];pending=len(core)-len(known)
  add(s,'core_proxy',100*sum(known)/len(core) if core and not pending else None,'complete' if core and not pending else 'no_configured_core_reference' if not core else 'pending_observations',unit='percent',minimum=100*sum(known)/len(core) if core else None,maximum=100*(sum(known)+pending)/len(core) if core else None,numerator=sum(known),denominator=len(core),formula='100 × tiendas con al menos una referencia de la canasta histórica / tiendas a las que aplica esa canasta. Proxy; no matriz núcleo oficial.',support=supports,scope='historical_configured_basket_proxy')
  for window in (30,90):
   records=[x for x in purchases if x['month'] in months and x['category']==cat and 0<=x['days_before_visit']<=window]
   weights=collections.defaultdict(float)
   for x in records:weights[(x['kobo_id'],x['month'])]+=x['net']
   base=num=unknown_presence=unknown_gate=0.0;store_weights=[]
   for row in rows:
    v=p['visits'][row['v']];weight=weights[(v['kobo_id'],v['month'])];gate=p['gates'][row['g']]['eligible'];presence=row['nd']['presence']
    store_weights.append([v['kobo_id'],v['month'],gate,presence,weight,weight if gate is True and presence==1 else 0])
    if gate is False:continue
    if gate is None:unknown_gate+=weight;continue
    base+=weight
    if presence==1:num+=weight
    elif presence is None:unknown_presence+=weight
   total=base+unknown_gate;complete=base>0 and not unknown_presence and not unknown_gate
   add(s,'weighted_'+str(window),100*num/base if complete else None,'complete' if complete else 'no_documented_weight_base' if not total else 'pending_observations',unit='percent',numerator=num,denominator=base,minimum=100*num/total if total else None,maximum=100*(num+unknown_presence+unknown_gate)/total if total else None,formula='100 × compra documentada de categoría en tiendas con marca / compra documentada de categoría en tiendas elegibles; ventana por visita de '+str(window)+' días.',scope='documented_purchase_window_scenario_not_official_configuration',window_days=window,invoice_rows=[x['source_row'] for x in records],store_weight_columns=['kobo_id','month','eligible','presence','documented_purchase_BOB','numerator_contribution_BOB'],store_weights=store_weights,excluded_invoice_rows_global=dict(invoice_status))
   eligible_keys={(p['visits'][row['v']]['kobo_id'],p['visits'][row['v']]['month']) for row in rows if p['gates'][row['g']]['eligible'] is True};fair_records=[x for x in records if (x['kobo_id'],x['month']) in eligible_keys];category_purchase=sum(x['net'] for x in fair_records);brand_purchase=sum(x['net'] for x in fair_records if fold(x['brand'])==fold(c['brand']));sh=s['sh'];share=sh.get('value')
   fair=brand_purchase/category_purchase/(share/100) if category_purchase>0 and sh['state']=='complete' and share and share>0 else None
   add(s,'fair_'+str(window),fair,'complete' if fair is not None else 'no_documented_purchase_base' if not category_purchase else 'zero_or_unresolved_shelf_share',unit='times',numerator=brand_purchase/category_purchase if category_purchase else None,denominator=share/100 if share is not None else None,formula='Participación de compra documentada / participación de estante; ventana '+str(window)+' días. No se invierte el cociente.',scope='documented_purchase_window_scenario_not_official_configuration',window_days=window,invoice_rows=[x['source_row'] for x in fair_records],purchase_universe='same_confirmed_eligible_store_months_as_shelf',shelf_series={'c':s['c'],'kind':s['kind'],'period':s['period']})
  # Category leader must have a complete denominator, never the largest partial subset.
  peers=[x for x in p['series'] if x['kind']==s['kind'] and x['period']==s['period'] and p['catalogue'][x['c']]['category']==c['category']];complete_shelf=all(x['sh']['state'] in ('complete','no_eligible_base') for x in peers);leader=max((x['sh'].get('value') or 0 for x in peers),default=0)
  family='bebidas_sin_alcohol' if cat.startswith('bsa_') else 'lacteos';group=p['conversion']['monthly'] if s['kind']=='month' else p['conversion']['annual_observed_months'];conv=next((x for x in group if x['period']==s['period'] and x['brand_code']==c['brand_code'] and x['family']==family),None)
  presence=s['nd'].get('value');relative=100*share/leader if complete_shelf and share is not None and leader>0 else None;execution=None;mode='pending_inputs'
  if s['nd']['state']=='complete' and relative is not None and conv:
   if conv['state']=='no_operating_brand_presence_base':execution=4/7*presence+3/7*relative;mode='no_cold_base_redistributed'
   elif conv['state']=='complete' and (conv.get('denominator') or 0)>=10:execution=.4*presence+.3*conv['value']+.3*relative;mode='40_30_30'
  add(s,'execution',execution,'complete' if execution is not None else 'pending_or_insufficient_component_base',unit='points',presence=presence,cold_conversion=conv.get('value') if conv else None,cold_denominator=conv.get('denominator') if conv else None,relative_shelf=relative,formula='40% presencia + 30% conversión + 30% estante relativo al líder; sin base de frío: 4/7 presencia + 3/7 estante. Se respeta n frío ≥ 10 para publicar el componente.',scope='captured_v329_formula_operational_application',mode=mode,support={'series_c':s['c'],'conversion':conv,'leader':leader,'all_category_shelf_complete':complete_shelf})
  # Conservative exact-size strata avoid inventing a tolerance for "similar sizes".
  observations=[x for x in price_rows if x['month'] in months and x['category']==cat and x['location']=='gondola'];ratios=[]
  for x in observations:
   if fold(x['brand'])!=fold(c['brand']):continue
   comparable=[y for y in observations if y['litres']==x['litres']]
   if len({fold(y['brand']) for y in comparable})<2:continue
   median=statistics.median(y['bs_per_litre'] for y in comparable)
   ratios.append({'source_row':x['source_row'],'sku':x['sku'],'value':100*x['bs_per_litre']/median,'price_bs':x['price_bs'],'litres':x['litres'],'category_median_bs_per_litre':median,'benchmark_rows':[y['source_row'] for y in comparable],'reference':x['reference']})
  add(s,'price_index',statistics.median(x['value'] for x in ratios) if ratios else None,'complete' if ratios else 'no_exact_size_competitive_benchmark',unit='points',formula='Mediana de 100 × precio Bs/litro del producto / mediana Bs/litro de categoría al mismo volumen exacto; góndola, al menos dos marcas. No se inventa tolerancia de tamaños.',scope='exact_volume_operational_price_index_not_certified_basket',observations=ratios,comparable_observations=len(ratios),price_source_rows=len(observations))
 result={'schema':'mindtec-extended-reconstruction/1','prepared':'2026-11-24','results':results,'invoice_coverage':dict(invoice_status),'resolved_price_observations':len(price_rows),'source_sha256':p['source_sha256'],'input_sources':{'detailed_workbook':{'filename':'envios_2026-11-23.xlsx','sha256':p['source_sha256']},'normalized_workbook':{'filename':'resultado_final_todo_2026-11-23.xlsx','sha256':hashlib.sha256((BASE/'resultado_final_todo_2026-11-23.xlsx').read_bytes()).hexdigest()},'invoices':invoice['provenance'],'census_published_aliases_sha256':hashlib.sha256((BASE/'skus_censo_resueltos_2026-11-24.csv').read_bytes()).hexdigest()},'reviewed_projection_sha256':hashlib.sha256((BASE/'soc24u/integrated-result.json').read_bytes()).hexdigest(),'master_sha256':hashlib.sha256((BASE/'skus_catalogo_2026-11-24.csv').read_bytes()).hexdigest(),'aliases_sha256':hashlib.sha256((BASE/'skus_resueltos_2026-11-24.csv').read_bytes()).hexdigest(),'code_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'limits':['These operational scopes are labelled separately from official panel configurations.','No purchase window, size tolerance or core matrix is asserted as certified when the captured configuration does not define it.','Purchase windows pool documented store-month exposures, not annual sales.','Canonical product brand is supplied by Scan; declared survey brand is preserved separately.','A missing denominator or unresolved observation never becomes zero.']}
 result['invoice_evidence']=invoice_evidence
 result['price_evidence']={str(r['source_row']):{k:v for k,v in r.items() if k!='reference'} for r in price_rows}
 for r in results:
  if r['value'] is not None:assert math.isfinite(r['value']) and r['value']>=0
 target=BASE/'extended-reviewed24.json';target.write_text(J(result),encoding='utf8');print(J({'complete':dict(collections.Counter(r['metric'] for r in results if r['state']=='complete')),'invoice_coverage':result['invoice_coverage'],'prices':len(price_rows)}))
 return result

if __name__=='__main__':build()
