"""Apply confirmed erroneous shelf repetitions; retain original source evidence."""
import copy,json
from pathlib import Path
import engine,integrated_report,shelf_share
BASE=Path('private/platform-recovered-2026-11-23');OUT=BASE/'v13024';SITE=Path('../../mindtec-web/app-site')
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):p.write_text(engine.canonical(v),encoding='utf-8')
def main():
 OUT.mkdir(exist_ok=True);path=BASE/'soc24u/integrated-result.json';before=OUT/'projection-before.json'
 if not before.exists():before.write_bytes(path.read_bytes())
 p=read(before);original=copy.deepcopy(p);decisions=[read(BASE/name) for name in ['visit-130-shelf-confirmation-2026-11-24.json','visit-130-juice-shelf-confirmation-2026-11-24.json']]
 affected=set();v=next(i for i,x in enumerate(p['visits']) if x=={'kobo_id':'130','month':'2026-10'})
 for d in decisions:
  category=p['categories'].index(d['category']);affected.add(category)
  inv=next(x for x in p['inventories'] if x['v']==v and x['category']==category)
  inv['original_inventory']=copy.deepcopy(inv)
  excluded={x['brand_code']:x for x in d['observations'] if x['disposition']=='exclude_erroneous_observation'}
  inv['excluded_erroneous_rows']=[];kept=[]
  for row in inv['rows']:
   if row['code'] in excluded:
    assert row['faces']==excluded[row['code']]['original_faces'];inv['excluded_erroneous_rows'].append(copy.deepcopy(row))
   else:kept.append(row)
  assert len(inv['excluded_erroneous_rows'])==len(excluded)
  inv.update(rows=kept,faces=d['corrected_category_faces'],known_faces=d['corrected_category_faces'],signals=[],state='complete',human_confirmation_sha256=engine.sha(engine.canonical(d)))
  assert sum(row['faces'] for row in kept)==d['corrected_category_faces']
  d['status']='integrated_local';d['application']['dashboard_updated']=True
  for st in p['stores']:
   if st['v']==v and p['catalogue'][st['c']]['category']==category:
    st['sh']['original_result']=copy.deepcopy(st['sh']);faces=sum(r['faces'] for r in kept if r['code']==p['catalogue'][st['c']]['brand_code'])
    st['sh'].update(brand_faces=faces,known_brand_faces=faces,human_confirmation_sha256=inv['human_confirmation_sha256'])
 for s in p['series']:
  c=p['catalogue'][s['c']]
  if c['category'] not in affected or not any(p['stores'][i]['v']==v for i in s['stores']):continue
  rows=[]
  for i in s['stores']:
   st=p['stores'][i];inv=p['inventories'][st['i']];gate=p['gates'][st['g']]
   rows.append(dict(id=i,brand=c['brand'],brand_code=c['brand_code'],category=p['categories'][c['category']],month=p['visits'][st['v']]['month'],eligible=gate['eligible'],state=inv['state'],brand_faces=st['sh']['brand_faces'],category_faces=inv['faces'],category_signals=gate['signals']))
  agg=shelf_share.aggregate(rows,s['period'],s['kind']);prior=copy.deepcopy(s['sh'])
  for k in list(s['sh']):
   if k in agg:s['sh'][k]=agg[k]
  s['sh'].update(original_result=prior,human_visit130_review=True)
 assert p['cells']==original['cells'] and p['answer_evidence']==original['answer_evidence']
 p['human_visit130_review']={'decisions':decisions,'date':'2026-11-24','excluded_faces':17,'scope':'shelf_only'}
 refs={'before':(before.read_bytes(),'.json'),'decisions':(engine.canonical(decisions).encode(),'.json'),'implementation':(engine.canonical({'code':Path(__file__).read_text(encoding='utf-8')}).encode(),'.json')};hashes={k:engine.sha(raw) for k,(raw,_) in refs.items()}
 with engine.Engine(OUT/'custody') as e:
  a=e.record_result(engine.canonical(decisions).encode(),p['policy'],{'kind':'shelf_human_correction','version':'1.0.0','reference_sources':hashes},[],{'excluded_faces':17},refs)
  p['sources']['shelf']={'run_id':a['run_id'],'snapshot_sha256':a['snapshot'],'ledger_head':e.verify(),'rule_version':'confirmed-shelf-repetitions/1.0.0','original_source':original['sources']['shelf']}
  write(path,p);a=e.record_result(engine.canonical(p).encode(),p['policy'],{'kind':'integrated_reconstruction','version':p['version'],'reference_sources':hashes},p['findings'],{'excluded_faces':17,'original_cells_unchanged':True},refs);receipt=dict(run_id=a['run_id'],snapshot_sha256=a['snapshot'],ledger_head=e.verify())
 target=OUT/('report-'+receipt['run_id'][:12]+'.html')
 if not target.exists():integrated_report.export(OUT/'custody',target,receipt['run_id'])
 dest=SITE/'source/integrated-cut-2026-11-24';(dest/'report.html').write_bytes(target.read_bytes());m=read(dest/'manifest.json');m.update(local_run_id=receipt['run_id'],projection_sha256=receipt['snapshot_sha256'],sources=p['sources'],human_visit130_review=p['human_visit130_review']);m['files']['report.html']=engine.sha(target.read_bytes());m['monthly_complete']['shelf']=sum(s['kind']=='month' and s['sh']['state']=='complete' for s in p['series']);write(dest/'manifest.json',m);write(OUT/'receipt.json',receipt)
 for d,name in zip(decisions,['visit-130-shelf-confirmation-2026-11-24.json','visit-130-juice-shelf-confirmation-2026-11-24.json']):write(BASE/name,d)
 print(engine.canonical({'excluded_faces':17,'hydrating_faces':3,'juice_faces':4,'receipt':receipt}))
if __name__=='__main__':main()
