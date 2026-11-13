"""Rebuild store-level Perfect Store from Scan exports; preserve rule uncertainty."""
from pathlib import Path
import argparse,collections, csv, hashlib, html, json, re, shutil, statistics, unicodedata

parser=argparse.ArgumentParser(description='Reconstruct a private Scan Perfect Store cut; never publish outputs.')
parser.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parent)
parser.add_argument('--downloads-dir',type=Path,default=Path.home()/'Downloads')
args=parser.parse_args()
ROOT = args.data_dir.resolve()
OUT = ROOT / 'Perfect_Store_reconstruido_2026-11-13'
OUT.mkdir(exist_ok=True)
DOWNLOADS = args.downloads_dir.resolve()
def read(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def norm(v): return re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', str(v or '')).encode('ascii','ignore').decode().lower())
def tokens(v): return str(v or '').split()
def num(v):
    try: return float(str(v).replace(',','.'))
    except (ValueError,TypeError): return None
def dump(name,obj): (OUT/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')
rawpath=DOWNLOADS/'cuestionarios_normalizados_2026-11-13.json'
raw=read(rawpath)
from scan_xlsx import read_scan_xlsx
x=read_scan_xlsx(DOWNLOADS/'resultado_final_2026-11-13.xlsx')
brandsheet=next(v for k,v in x.items() if 'marcas' in k)
configs=read(ROOT/'Configuracion_observada_MindTEC_2026-11-12/configuracion_clientes_observada.json')['clientes']
prior=read(ROOT/'Colecta_descargada_2026-11-12/conciliacion_y_alcance.json')
excluded={r['id']:r for r in prior['exclusiones_coincidentes_con_auditoria_previa']}
visits=[e for e in raw['envios'] if str(e['envioKobo']) not in excluded]
assert len(visits)==108 and len({(e['fechaVisita'][:7],e['codigoTienda']) for e in visits})==108
vmap={str(e['envioKobo']):e for e in visits}
company_alias={'dbbsalvietti':'salvietti_ddb','salvietti':'salvietti_ddb','salviettiddb':'salvietti_ddb','vemassaalimentosybebidass a':'vemassa','pilandina':'pil_andina'}
def company_code(v):
    n=norm(v)
    if n.startswith('vemassa'): return 'vemassa'
    return company_alias.get(n,n)
company_by_brand={}
cube=[]
for mo in ['2026-09','2026-10']:
    p=DOWNLOADS/f'cubo_embol_{mo}.csv'
    rows=list(csv.DictReader(p.open(encoding='utf-8-sig',newline='')))
    cube+=rows
    for r in rows:
        if r['marca'] and r['empresa'] and r['empresa']!='Otras / independientes':
            company_by_brand[norm(r['marca'])]=company_code(r['empresa'])
h=(ROOT/'MindTEC_KPI_originales_restaurados.html').read_text(encoding='utf-8')
old=json.loads(re.search(r'<script id="data" type="application/json">(.*?)</script>',h,re.S)[1])
for k in old['kpis']:
    if k[0] and k[0]!='Otras / independientes': company_by_brand.setdefault(norm(k[2]),company_code(k[0]))
company_by_brand.update({'pacena':'cbn','cocacola':'embol','pil':'pil_andina'})
catalog={}
present=collections.defaultdict(list)
for r in brandsheet[1:]:
    key=(r.get('G',''),r.get('H',''),r.get('I',''))
    if not all(key): continue
    catalog[key]=True
    present[(r.get('B'),r.get('C'),key)].append(r)
catnames={'bsa_gaseosas':'gaseosas','bsa_agua':'agua sin gas','bsa_agua_saborizada':'agua saborizada','bsa_energizantes':'energizantes','bsa_hidratantes':'hidratantes','bsa_jugos':'jugos','lac_bebida_lactea':'bebida láctea','lac_leche_soya':'leche de soya','lac_leche_natural':'leche natural','lac_leche_saborizada':'leche saborizada','lac_leche_deslactosada':'leche deslactosada','bsa_gaseosas_sin_azucar':'gaseosas sin azúcar','bsa_agua_con_gas':'agua con gas','bsa_agua_funcional':'agua funcional'}
# Explicit label equivalences only. No sku_N catalogue crosswalk is assumed:
# the current Excel exposes incompatible SKU descriptions between form versions.
aliases={
 'Coca-Cola PET. 300ml':'Coca-Cola PET No Retornable 300 ml',
 'Coca-Cola Vidrio 190ml':'Coca-Cola Vidrio Retornable 190 ml',
 'Coca-Cola PET. RET. 2L':'Coca-Cola PET Retornable 2 L',
 'Coca-Cola PET. NO RET. 2L':'Coca-Cola PET No Retornable 2 L',
 'Coca-Cola PET. RET. 2.5L':'Coca-Cola PET Retornable 2,5 L',
 'Coca-Cola PET. NO RET. 2.5L':'Coca-Cola PET No Retornable 2,5 L',
 'Pepsi PET. 250ml':'Pepsi 250 ml','Pepsi PET. 2L':'Pepsi 2 L',
 'Cascada PET. 2L':'Cascada PET. 2L','Cascada PET 2 L':'Cascada PET. 2L',
 'Leche natural Pil en bolsa 900ml':'Leche natural Pil en bolsa 900ml',
 'Leche deslactosada Pil en bolsa 800ml':'Pil Deslactosada Sachet 800 ml',
 'Leche entera Pil en bolsa 1.1L':'Pil Leche Entera Sachet 1,1 L',
 'Leche Vaquita en bolsa 120ml':'Vaquita Leche Bolsa 120 ml',
 'Chiqui choc/avena/frutilla en bolsa 140ml':'Chiqui Choc/Avena/Frutilla Bolsa 140 ml',
 'Leche natural Kream en bolsa 946 ml':'Kream Leche Natural 946 ml',
 'Leche deslactosada Kream en bolsa 800ml':'Kream Deslactosada 800 ml',
 'Delizia deslactosada en bolsa 800 ml':'Delizia Leche Deslactosada 800 ml',
 'Valle Nectar PET. 2L':'Del Valle Néctar PET 2 L'}
def canon_price(label): return norm(aliases.get(label,label))
def price_brand(label):
    n=canon_price(label)
    for brand in ['Coca-Cola','Pilfrut','Vaquita','Chiqui','Powerade','Aquarius','Del Valle','Cascada','Pepsi','Kream','Delizia','Volt']:
        if norm(brand) in n: return norm(brand)
    return 'pil' if 'pil' in n else None
ref_by_brand={}
for cat,code,brand in catalog:
    co=company_by_brand.get(norm(brand))
    conf=next((c for c in configs if company_code(c['empresa'])==co),None)
    if conf:
        # Use the brand of the configured price item, not the owner's entire basket.
        refs=[s for s in conf['skus'] if price_brand(s)==norm(brand)]
        if refs: ref_by_brand[norm(brand)]=refs

def prepare(e):
    fields={r['ruta']:r for r in e['respuestas']}
    groups=collections.defaultdict(dict)
    for r in e['respuestas']:
        if r['ruta'].startswith('rep_'):
            g,f=r['ruta'].split('/',1);groups[g][f]=r
    return fields,groups
prepared={str(e['envioKobo']):prepare(e) for e in visits}
def matching(fields,suffix): return [r for p,r in fields.items() if p.endswith('/'+suffix)]
def evidence(rs): return [{'ruta':r['ruta'],'pregunta':r['pregunta'],'valor':r['valor']} for r in rs]
def component(name,value,why,rs=(),state=None):
    return dict(componente=name,estado=state or ('medido' if value is not None else 'pendiente'),valor=value,peso=1,motivo=why,fuentes=evidence(rs))
def na(name,why,rs=()): return component(name,None,why,rs,'no aplica')

details=[]
for cat,code,brand in sorted(catalog):
    co=company_by_brand.get(norm(brand))
    refs=ref_by_brand.get(norm(brand),[])
    for e in visits:
        eid=str(e['envioKobo']);fields,groups=prepared[eid]
        gate=matching(fields,'vende_'+cat)
        eligible=gate[0]['valor']=='si' if gate and gate[0]['valor'] in ('si','no') else None
        if eligible is False: continue
        choices=matching(fields,'marcas_'+cat)
        pr=[fs for g,fs in groups.items() if g.startswith('rep_'+cat+'[') and fs.get('marca_act_'+cat,{}).get('valor')==code]
        # Excel internal envio IDs are not Kobo IDs. Presence is rebuilt from
        # original choices/repeats instead of joining these different keys.
        has=any(code in tokens(r['valor']) for r in choices) or bool(pr)
        if code in ('otras','otro','otras_marcas'):
            has=any(norm(brand) in norm(r['valor']) for fs in pr for r in fs.values() if 'otr' in r['ruta'] or 'lbl' in r['ruta'])
        pres=has if eligible is True else None
        prs=[r for fs in pr for f,r in fs.items() if f in ('marca_act_'+cat,'marca_lbl_'+cat)]
        cs=[component('Presencia',int(pres) if pres is not None else None,'Marca declarada en la subcategoría; universo: vende la categoría.',gate+choices+prs)]
        # Explicit selection in the price basket is evidence of any reference SKU.
        if not co:
            cs.append(component('SKU núcleo',None,'Empresa sin homologar: no se puede determinar la canasta de referencia aplicable.'))
        elif not refs:
            cs.append(na('SKU núcleo','Sin SKU de esta marca en la canasta de referencia del cliente observado; no se exige a la competencia.'))
        else:
            selected=[]
            for g,fs in groups.items():
                if g.startswith('rep_precio[') and 'sku_precio_label' in fs: selected.append(fs['sku_precio_label'])
            selected_refs=[r for r in selected if canon_price(r['valor']) in {canon_price(s) for s in refs}]
            answered=matching(fields,'skus_precio_catalogo')+matching(fields,'skus_precio')
            val=int(bool(selected_refs)) if selected or answered else None
            cs.append(component('SKU núcleo',val,'Al menos una referencia de la marca seleccionada en la canasta de precios. Equivalencias explícitas de etiquetas; configuración actual aplicada retrospectivamente, sin versión histórica certificada.',selected_refs or selected or answered))
        cooler=[]; access=[]; unknown_cooler=[]
        for g,fs in groups.items():
            if not g.startswith('rep_enfriador['): continue
            cooler.extend(fs.values())
            typ=norm(fs.get('tipo_enfriador',{}).get('valor'))
            # Reconstructed observed access rule: Coca-Cola may use any operating
            # vertical cooler; other brands cannot use a Coca-Cola exclusive cooler.
            if typ and typ not in ('neveravertical','enfriadorvertical','neveracasera'): continue
            on=fs.get('enfriador_encendido',{}).get('valor')
            sponsor=fs.get('enfriador_patrocinado',{}).get('valor')
            owner=norm(fs.get('marca_enfriador',{}).get('valor'))
            if not typ or (norm(brand)!='cocacola' and (sponsor not in ('si','no') or sponsor=='si' and not owner)):
                unknown_cooler.append(g);continue
            blocked=norm(brand)!='cocacola' and sponsor=='si' and owner=='cocacola'
            if not blocked and on=='si': access.append(g)
            elif not blocked and on not in ('si','no'): unknown_cooler.append(g)
        coldrows=[]; coldvals=[]
        for g,fs in groups.items():
            if g.startswith('rep_caras_frias['):
                r=fs.get('marca_fria_actual');v=fs.get('caras_frias')
                if r and v and r['valor']==code:
                    coldrows += [r,v];coldvals.append(num(v['valor']))
                continue
            if not g.startswith('rep_frio_'+cat+'['): continue
            r=fs.get('marca_frio_act_'+cat)
            if r and r['valor']==code:
                v=fs.get('caras_frio_'+cat)
                if v: coldrows += [r,v];coldvals.append(num(v['valor']))
        cooler_gate=matching(fields,'hay_enfriadores')
        if access:
            enumeration=matching(fields,'n_marcas_frias')+matching(fields,'n_frio_'+cat)
            positive=any(v is not None and v>0 for v in coldvals)
            v=1 if positive else None if any(v is None for v in coldvals) else 0 if coldvals or pres is False or enumeration else None
            cs.append(component('Frío',v,'Equipo vertical o nevera casera operativo accesible según regla reconstruida. Octubre: caras por subcategoría. Septiembre: el formulario enumera caras de marca sin subcategoría. No existe vínculo cara-equipo.',cooler+coldrows+enumeration))
        elif unknown_cooler or (not cooler and not cooler_gate):
            cs.append(component('Frío',None,'No se puede resolver equipo operativo accesible.',cooler+cooler_gate))
        else: cs.append(na('Frío','Sin equipo vertical o nevera casera operativo accesible para esta marca; se excluye del denominador.',cooler+cooler_gate))
        popgate=matching(fields,'tiene_material_marketing')
        poprs=[r for p,r in fields.items() if re.search(r'/(marcas|empresas)_material_',p)]
        pcodes=[t for r in poprs for t in tokens(r['valor'])]
        popcompanies={company_by_brand.get(norm(t)) or company_code(t) for t in pcodes}
        if not co: cs.append(component('POP',None,'Falta homologar empresa propietaria de esta marca.',popgate+poprs))
        elif popgate and popgate[0]['valor']=='no': cs.append(component('POP',0,'La tienda declara no tener material de marketing.',popgate))
        elif poprs or (popgate and popgate[0]['valor']=='si'):
            cs.append(component('POP',int(co in popcompanies),'Material de alguna marca de la empresa propietaria. Universo Perfect Store: todas las tiendas elegibles, aunque la marca no esté presente.',popgate+poprs))
        else: cs.append(component('POP',None,'Falta respuesta de material de marketing.',popgate))
        stock=[]
        for g,fs in groups.items():
            if g.startswith('rep_stock_empresa[') and company_code(fs.get('empresa_actual_stock',{}).get('valor'))==co:
                stock+=list(fs.values())
        buys=matching(fields,'empresas_compra')
        st=next((r for r in stock if r['ruta'].endswith('/hay_quiebre_empresa')),None)
        if st and st['valor'] in ('si','no'): cs.append(component('Sin quiebre',int(st['valor']=='no'),'Declaración de quiebre de empresa, no inventario por SKU.',stock))
        elif co and buys and co not in {company_code(t) for t in tokens(buys[0]['valor'])}: cs.append(na('Sin quiebre','No declara comprar a la empresa; se excluye del denominador.',buys))
        else: cs.append(component('Sin quiebre',None,'Falta empresa homologada o respuesta de quiebre para una empresa compradora.',stock+buys))
        known=[c for c in cs if c['estado']=='medido'];pending=[c for c in cs if c['estado']=='pendiente']
        n=sum(c['valor'] for c in known);den=len(known);miss=len(pending)
        score=100*n/den if den and not miss and eligible is True else None
        lo=100*n/(den+miss) if den+miss else None
        hi=100*(n+miss)/(den+miss) if den+miss else None
        details.append(dict(mes=e['fechaVisita'][:7],categoria=catnames.get(cat,cat),codigo_categoria=cat,marca=brand,codigo_marca=code,empresa=co,id_envio=eid,sticker=e['codigoTienda'],tienda=(e.get('tiendaMaestro') or {}).get('nombre') or (e.get('puntoVenta') or {}).get('normalizado') or (e.get('puntoVenta') or {}).get('original') or '',elegible=eligible,componentes=cs,numerador=n,denominador=den,pendientes=miss,perfect_store=score,minimo=lo,maximo=hi,referencias_configuradas=refs,version_regla='PS-OPER-2026-11-13.1'))

groups=collections.defaultdict(list)
for r in details: groups[(r['mes'],r['categoria'],r['marca'])].append(r)
historical={}
for v in old['dashboardLive'].values():
    historical[(v['month'],norm(v['cat']),norm(v['brand']))]=v['values'][0]
published_cut=read(OUT/'captura_panel_perfect_store.json')
rankbrands=published_cut['rankbrands']
livevals=published_cut['livevals']
live={(m,norm(b)):v for m,vs in livevals.items() for b,v in zip(rankbrands,vs)}
summary=[]
for (mo,cat,brand),rows in sorted(groups.items()):
    vals=[r['perfect_store'] for r in rows if r['perfect_store'] is not None]
    unknown=sum(r['elegible'] is None for r in rows)
    counts={c:{'cumple':sum(z['valor']==1 and z['estado']=='medido' for r in rows for z in r['componentes'] if z['componente']==c),'medidos':sum(z['estado']=='medido' for r in rows for z in r['componentes'] if z['componente']==c),'no_aplica':sum(z['estado']=='no aplica' for r in rows for z in r['componentes'] if z['componente']==c),'pendientes':sum(z['estado']=='pendiente' for r in rows for z in r['componentes'] if z['componente']==c)} for c in ['Presencia','SKU núcleo','Frío','POP','Sin quiebre']}
    complete=len(vals)==len(rows) and not unknown
    result=statistics.mean(vals) if complete and vals else None
    published=live.get((mo,norm(brand))) if cat=='gaseosas' else None
    summary.append(dict(mes=mo,categoria=cat,marca=brand,empresa=rows[0]['empresa'],tiendas=len(rows),elegibilidad_pendiente=unknown,tiendas_calculadas=len(vals),resultado=result,promedio_parcial=statistics.mean(vals) if vals else None,minimo=statistics.mean(r['minimo'] for r in rows if r['minimo'] is not None) if not unknown else None,maximo=statistics.mean(r['maximo'] for r in rows if r['maximo'] is not None) if not unknown else None,componentes=counts,publicado_actual=published,publicado_historico=historical.get((mo,norm(cat),norm(brand))),diferencia_publicado_menos_reconstruido=published-result if published is not None and result is not None else None,alcance='Reconstrucción operativa; aplicación retrospectiva de reglas/configuración actuales. No certifica versión histórica oficial.'))
dump('detalle_por_tienda.json',details);dump('resumen_por_marca_mes.json',summary)
dump('reglas_y_fuentes.json',dict(version='PS-OPER-2026-11-13.1',generado=raw['generado'],formula_tienda='100 × suma de cumplimientos / número de componentes aplicables medidos; si hay pendientes, resultado completo no disponible y se muestran límites.',formula_marca='Media aritmética de puntajes de tiendas elegibles, sin ponderar por compras o superficie. No promedio de porcentajes agregados de componentes.',pesos='1 por componente aplicable; reconstrucción de la regla visible, sin exportación del motor ni versión histórica certificada.',exclusiones=list(excluded.values()),etiquetas_equivalentes=aliases,empresa_por_marca=company_by_brand,configuracion_clientes=configs,publicados_actuales=livevals,orden_publicados=rankbrands,observaciones=published_cut.get('observaciones',[])))
for name,rows in [('resumen_por_marca_mes.csv',summary),('detalle_por_tienda.csv',details)]:
    flat=[]
    for r in rows:
        z={k:v for k,v in r.items() if k not in ('componentes','referencias_configuradas')}
        for c in r['componentes'] if isinstance(r['componentes'],list) else []:
            z[c['componente']]=c['valor'] if c['estado']=='medido' else c['estado'];z[c['componente']+' motivo']=c['motivo'];z[c['componente']+' fuente']=json.dumps(c['fuentes'],ensure_ascii=False)
        flat.append(z)
    with (OUT/name).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(dict.fromkeys(k for r in flat for k in r)));w.writeheader();w.writerows(flat)
sources=[]
for p in [rawpath,DOWNLOADS/'resultado_final_2026-11-13.xlsx',DOWNLOADS/'cubo_embol_2026-09.csv',DOWNLOADS/'cubo_embol_2026-10.csv',DOWNLOADS/'MindTEC-panel-CBN-Pepsi-2026-11-13.html',DOWNLOADS/'MindTEC-panel-EMBOL-Coca-Cola-2026-11-13.html',ROOT/'Configuracion_observada_MindTEC_2026-11-12/configuracion_clientes_observada.json']:
    shutil.copy2(p,OUT/p.name);sources.append(dict(archivo=p.name,sha256=hashlib.sha256(p.read_bytes()).hexdigest()))
dump('manifiesto.json',dict(corte='2026-11-13',exportados=112,incluidos=108,meses=collections.Counter(e['fechaVisita'][:7] for e in visits),marcas=len(set(r['marca'] for r in summary)),combinaciones_marca_categoria_mes=len(summary),filas_tienda=len(details),resultados_completos=sum(r['resultado'] is not None for r in summary),fuentes=sources))
for r in summary:
    if r['marca'] in ('7up','Coca-Cola') and r['categoria']=='gaseosas': print(json.dumps(r,ensure_ascii=False))
print('Results',len(summary),'details',len(details),'complete',sum(r['resultado'] is not None for r in summary))
