"""Apply explicit negative photo-review entries without erasing original evidence."""
import copy,json,re,unicodedata,collections
from pathlib import Path
import engine,integrated_report,shelf_share
BASE=Path('private/platform-recovered-2026-11-23');OUT=BASE/'photo-review24';SITE=Path('../../mindtec-web/app-site')
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):p.write_text(engine.canonical(v),encoding='utf-8')
def norm(v):return re.sub(r'[^a-z0-9]+',' ',''.join(c for c in unicodedata.normalize('NFD',str(v)).lower() if not unicodedata.combining(c))).strip()
def main():
 notes=read(OUT/'review-notes.json');path=BASE/'soc24u/integrated-result.json';before=OUT/'projection-before-bulk.json'
 if not before.exists():before.write_bytes(path.read_bytes())
 p=read(before);original=copy.deepcopy(p);aliases={norm(c['brand']):c['brand_code'] for c in p['catalogue']}
 aliases.update({'redbull':'red_bull','cin jugos':'cin','juguito pil':'pil_juguito','cascada sabores':'cascada','pura':'pura_vida','del calle':'del_valle','coca cola sin azucar':'coca_cola'})
 blocks=[]
 for row in notes['rows']:
  current=None
  for line in row['not_seen'].splitlines():
   line=line.strip()
   if not line or line=='-':continue
   is_child=line.startswith(('-', '•')) or bool(re.match(r'^\d',line))
   if is_child and current is not None:current['presentations'].append(line.lstrip('-• ').strip());continue
   current=dict(kobo_id=row['matched_visits'][0],month='2026-10',sticker=row['sticker'],sheet=row['sheet'],cell=row['not_seen_cell'],brand_text=line,brand_code=aliases.get(norm(line)),presentations=[]);blocks.append(current)
 for b in blocks:
  b['kind']='presentation_exclusion' if b['presentations'] else 'whole_brand_exclusion';b['source_sha256']=notes['source_sha256']
  if norm(b['brand_text'])=='pura vida agua':b.update(brand_code='pura_vida',product_category='Agua sin gas')
  if norm(b['brand_text'])=='chiquichoc':b.update(kind='named_product_exclusion',product_name_key='chiquichoc')
 whole=collections.defaultdict(dict)
 for b in blocks:
  if b['kind']=='whole_brand_exclusion' and b['brand_code']:whole[b['kobo_id']][b['brand_code']]=b
 changes=[];affected=set()
 for inv in p['inventories']:
  visit=p['visits'][inv['v']]
  if visit['month']!='2026-10' or inv['eligible'] is not True:continue
  remove=[r for r in inv['rows'] if r['code'] in whole[visit['kobo_id']]]
  if not remove:continue
  inv['before_photo_review']=copy.deepcopy(inv);inv.setdefault('excluded_photo_rows',[]);kept=[]
  for r in inv['rows']:
   if r in remove:
    note=whole[visit['kobo_id']][r['code']];inv['excluded_photo_rows'].append(dict(original_row=r,review=note));changes.append(dict(**visit,category=p['categories'][inv['category']],brand_code=r['code'],excluded_faces=r['faces'],review_cell=note['cell'],source_sha256=notes['source_sha256']))
   else:kept.append(r)
  inv['rows']=kept;inv['known_faces']=sum(r['faces'] or 0 for r in kept)
  # Resolve enumeration only when the remaining repetitions equal the explicit selection.
  selected=None
  for ref in p['evidence_sets'][inv['evidence_set']]:
   a=p['answer_evidence'].get(ref)
   if a and a['route'].endswith('/marcas_'+p['categories'][inv['category']]):selected=set(str(a['value'] or '').split())
  if selected is not None and selected=={r['code'] for r in kept} and all(r['faces'] is not None for r in kept):
   inv['signals']=[s for s in inv['signals'] if s not in ['brand_enumeration_incomplete','selected_brands_and_repetitions_disagree']]
  if not inv['signals'] and all(r['faces'] is not None for r in kept):inv.update(state='complete',faces=inv['known_faces'])
  else:inv.update(state='pending',faces=None)
  affected.add((inv['v'],inv['category']))
 for st in p['stores']:
  inv=p['inventories'][st['i']]
  if (st['v'],inv['category']) not in affected:continue
  st['sh']['before_photo_review']=copy.deepcopy(st['sh']);code=p['catalogue'][st['c']]['brand_code'];known=sum(r['faces'] or 0 for r in inv['rows'] if r['code']==code)
  st['sh'].update(brand_faces=known if inv['state']=='complete' else None,known_brand_faces=known)
 for s in p['series']:
  if not any((p['stores'][i]['v'],p['catalogue'][s['c']]['category']) in affected for i in s['stores']):continue
  c=p['catalogue'][s['c']];rows=[]
  for i in s['stores']:
   st=p['stores'][i];inv=p['inventories'][st['i']];g=p['gates'][st['g']];rows.append(dict(id=i,brand=c['brand'],brand_code=c['brand_code'],category=p['categories'][c['category']],month=p['visits'][st['v']]['month'],eligible=g['eligible'],state=inv['state'],brand_faces=st['sh']['brand_faces'],category_faces=inv['faces'],category_signals=g['signals']))
  agg=shelf_share.aggregate(rows,s['period'],s['kind']);prior=copy.deepcopy(s['sh'])
  for k in list(s['sh']):
   if k in agg:s['sh'][k]=agg[k]
  s['sh']['before_photo_review']=prior
 assert p['cells']==original['cells'] and p['cold_inventories']==original['cold_inventories']
 # Remove confirmed whole-brand records and unambiguous presentation matches from active product views.
 productfile=SITE/'source/product-evidence-2026-11-24/result.json';productbefore=OUT/'products-before-bulk.json'
 if not productbefore.exists():productbefore.write_bytes(productfile.read_bytes())
 products=read(productbefore);excluded=[];active=[]
 for link in products['links']:
  matches=[]
  if link['month']=='2026-10':
   code=aliases.get(norm(link.get('declared_brand') or link.get('canonical_brand')))
   for b in blocks:
    if b['kobo_id']!=link['kobo_id']:continue
    if b['kind']=='named_product_exclusion':
     if norm(link.get('canonical_label') or '').replace(' ','').startswith(b['product_name_key']):matches.append(b)
     continue
    if not b['brand_code'] or b['brand_code']!=code:continue
    if b.get('product_category') and link.get('category')!=b['product_category']:continue
    if b['kind']=='whole_brand_exclusion':matches.append(b);continue
    label=norm(link.get('selected_label') or link.get('canonical_label') or '')
    for desc in b['presentations']:
     # Exact text tokens only; ambiguous descriptions remain explicit exclusion instructions.
     tokens=norm(desc).split()
     if tokens and all(t in label.split() for t in tokens):matches.append(b);break
  if matches:excluded.append(dict(**link,photo_exclusion=matches))
  else:active.append(link)
 products['links']=active;products['excluded_photo_links']=excluded
 still={(r['kobo_id'],r['month'],r['canonical_label']) for r in active if r['entity']=='brands' and r.get('canonical_label')}
 products['product_presence']=[r for r in products['product_presence'] if (r['kobo_id'],r['month'],r['canonical_label']) in still]
 products['photo_exclusion_source_sha256']=notes['source_sha256'];write(productfile,products)
 report=dict(schema='mindtec-photo-exclusions/1',date='2026-11-24',source_sha256=notes['source_sha256'],blocks=blocks,shelf_changes=changes,excluded_product_links=len(excluded),affected_inventories=len(affected),excluded_known_shelf_faces=sum(x['excluded_faces'] or 0 for x in changes),presentation_instructions=sum(b['kind']=='presentation_exclusion' for b in blocks),unmapped_brand_texts=sorted({b['brand_text'] for b in blocks if not b['brand_code'] and not b.get('product_name_key')}),scope='Originals retained; whole-brand shelf exclusions and exact product matches applied. SKU-only exclusions never automatically remove aggregate brand faces. Cold not changed.');write(OUT/'exclusions.json',report);p['photo_exclusion_review']=report
 refs={'before':(before.read_bytes(),'.json'),'photo_review':((OUT/'review-source.xlsx').read_bytes(),'.xlsx'),'exclusions':((OUT/'exclusions.json').read_bytes(),'.json'),'implementation':(engine.canonical({'code':Path(__file__).read_text(encoding='utf-8')}).encode(),'.json')};hashes={k:engine.sha(raw) for k,(raw,_) in refs.items()}
 with engine.Engine(OUT/'custody') as e:
  a=e.record_result(engine.canonical(report).encode(),p['policy'],{'kind':'shelf_photo_exclusions','version':'1.0.0','reference_sources':hashes},[],{'affected_inventories':len(affected)},refs)
  p['sources']['shelf']=dict(run_id=a['run_id'],snapshot_sha256=a['snapshot'],ledger_head=e.verify(),rule_version='photo-review-exclusions/1.0.0',original_source=original['sources']['shelf']);write(path,p)
  a=e.record_result(engine.canonical(p).encode(),p['policy'],{'kind':'integrated_reconstruction','version':p['version'],'reference_sources':hashes},p['findings'],{'photo_exclusions':True},refs);receipt=dict(run_id=a['run_id'],snapshot_sha256=a['snapshot'],ledger_head=e.verify())
 target=OUT/('report-'+receipt['run_id'][:12]+'.html')
 if not target.exists():integrated_report.export(OUT/'custody',target,receipt['run_id'])
 dest=SITE/'source/integrated-cut-2026-11-24';(dest/'report.html').write_bytes(target.read_bytes());m=read(dest/'manifest.json');m.update(local_run_id=receipt['run_id'],projection_sha256=receipt['snapshot_sha256'],sources=p['sources'],photo_exclusion_review={k:v for k,v in report.items() if k not in ['blocks','shelf_changes']});m['files']['report.html']=engine.sha(target.read_bytes());write(dest/'manifest.json',m);write(OUT/'receipt.json',receipt)
 print(engine.canonical({k:v for k,v in report.items() if k not in ['blocks','shelf_changes']}))
if __name__=='__main__':main()
