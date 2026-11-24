"""Apply the user's exact September Soy face attribution; preserve original cells."""
import copy,json,hashlib
from pathlib import Path
import engine,integrated_report

ROOT=Path(__file__).resolve().parent
BASE=ROOT/'private/platform-recovered-2026-11-23'
SITE=ROOT.parent.parent/'mindtec-web/app-site'
OUT=BASE/'soy24'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def write(p,v):p.write_text(engine.canonical(v),encoding='utf-8')

def main():
 OUT.mkdir(exist_ok=True)
 path=BASE/'soc24u/integrated-result.json';before=OUT/'projection-before.json'
 if not before.exists():before.write_bytes(path.read_bytes())
 p=read(before);original=copy.deepcopy(p)
 ci=next(i for i,c in enumerate(p['catalogue']) if c['brand_code']=='soy' and p['categories'][c['category']]=='lac_leche_soya')
 changes=[];faces_by_visit={}
 for inv in p['inventories']:
  if p['categories'][inv['category']]!='lac_leche_soya' or p['visits'][inv['v']]['month']!='2026-09' or not inv['eligible']:continue
  for row in inv['rows']:
   if row['code']!='pil' or not row['faces']:continue
   changes.append(dict(**p['visits'][inv['v']],faces=row['faces'],group=row['group'],evidence_set=inv['evidence_set'],original_code='pil',confirmed_code='soy'))
   faces_by_visit[inv['v']]=faces_by_visit.get(inv['v'],0)+row['faces']
   row.update(original_code=row['code'],original_label=row['label'],code='soy',label='Soy',attribution_basis='human_confirmed_2026_11_24')
 assert len(faces_by_visit)==20 and sum(x['faces'] for x in changes)==40
 decision=dict(schema='mindtec-human-face-attribution/1',date='2026-11-24',month='2026-09',category='lac_leche_soya',
  confirmed_brand='Soy',confirmed_faces=40,source_code='pil',scope='shelf_faces_only',
  exact_user_confirmation='corrigela , esas caras si son de Soy yo mismo los comprobe',
  basis='El usuario confirma personalmente la atribución de las 40 caras previamente registradas como Pil a Soy.',
  original_projection_sha256=hashlib.sha256(before.read_bytes()).hexdigest(),changes=changes,
  limits='La confirmación atribuye caras de estante. No valida ni sustituye los códigos SKU, la declaración original de distribución, el frío o la configuración de Perfect Store.')
 write(OUT/'confirmation.json',decision);confirmation_sha=engine.sha(engine.canonical(decision))
 for st in p['stores']:
  if st['c']==ci and st['v'] in faces_by_visit:
   st['sh'].update(original_brand_faces=st['sh']['brand_faces'],brand_faces=faces_by_visit[st['v']],known_brand_faces=faces_by_visit[st['v']],human_confirmation_sha256=confirmation_sha)
 for s in p['series']:
  if s['c']!=ci or not any(p['stores'][i]['v'] in faces_by_visit for i in s['stores']):continue
  s['sh']['original_result']=copy.deepcopy(s['sh'])
  if s['sh']['state']=='complete':
   s['sh']['numerator']=sum(p['stores'][i]['sh']['brand_faces'] or 0 for i in s['stores'])
   s['sh']['value']=100*s['sh']['numerator']/s['sh']['denominator']
  s['sh']['human_confirmation_sha256']=confirmation_sha
 sep=next(s for s in p['series'] if s['c']==ci and s['period']=='2026-09' and s['kind']=='month')
 assert sep['sh']['numerator']==40 and sep['sh']['denominator']==44
 assert abs(sep['sh']['value']-100*40/44)<1e-12
 assert p['cells']==original['cells'] and p['answer_evidence']==original['answer_evidence']
 p['human_soy_face_review']=dict(confirmation=decision,confirmation_sha256=confirmation_sha)
 refs={'confirmation':((OUT/'confirmation.json').read_bytes(),'.json'),'original_projection':(before.read_bytes(),'.json'),'implementation':(engine.canonical({'code':Path(__file__).read_text(encoding='utf-8')}).encode(),'.json')}
 hashes={k:engine.sha(v[0]) for k,v in refs.items()}
 with engine.Engine(OUT/'custody') as e:
  a=e.record_result(engine.canonical(decision).encode(),p['policy'],{'kind':'shelf_face_human_attribution','version':'1.0.0','reference_sources':hashes},[],{'confirmed_faces':40,'visits':20},refs)
  p['sources']['shelf']=dict(run_id=a['run_id'],snapshot_sha256=a['snapshot'],ledger_head=e.verify(),rule_version='shelf-face-attribution/1.0.0',original_source=original['sources']['shelf'])
  write(path,p)
  a=e.record_result(engine.canonical(p).encode(),p['policy'],{'kind':'integrated_reconstruction','version':p['version'],'human_face_confirmation_sha256':confirmation_sha,'reference_sources':hashes},p['findings'],{'soy_shelf_september':sep['sh']['value'],'original_cells_unchanged':True},refs)
  receipt=dict(run_id=a['run_id'],snapshot_sha256=a['snapshot'],ledger_head=e.verify())
 target=OUT/('report-'+receipt['run_id'][:12]+'.html')
 if not target.exists():integrated_report.export(OUT/'custody',target,receipt['run_id'])
 dest=SITE/'source/integrated-cut-2026-11-24';(dest/'report.html').write_bytes(target.read_bytes())
 m=read(dest/'manifest.json');m.update(local_run_id=receipt['run_id'],projection_sha256=receipt['snapshot_sha256'],sources=p['sources'],human_soy_face_review=p['human_soy_face_review']);m['files']['report.html']=engine.sha(target.read_bytes());write(dest/'manifest.json',m)
 write(OUT/'receipt.json',receipt)
 print(engine.canonical(dict(soy_shelf=sep['sh'],receipt=receipt)))

if __name__=='__main__':main()
