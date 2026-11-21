"""Join conversion once per brand/family, preserving source cohort and shared evidence."""
import copy
import engine, cold_conversion


def attach(base, source, metadata):
 r=copy.deepcopy(base);ps=r['sources']['perfect_store']
 if source.get('source_ps_run_id')!=ps['run_id'] or source.get('source_ps_snapshot_sha256')!=ps['snapshot_sha256'] or source.get('source_sha256')!=r['source_sha256'] or source.get('unit')!='brand_within_family':raise ValueError('Conversion source or unit differs')
 if source['source_distribution']['run_id']!=r['sources']['distribution']['run_id'] or source['source_distribution']['snapshot_sha256']!=r['sources']['distribution']['snapshot_sha256']:raise ValueError('Conversion presence execution differs')
 if 'cold' not in r['sources'] or any(source['source_cold'][k]!=r['sources']['cold'][k] for k in ['run_id','snapshot_sha256']):raise ValueError('Conversion cold execution differs')
 for name in ['cells','answer_evidence']:
  for key,value in source[name].items():
   if engine.sha(engine.canonical(value))!=key or key in r[name] and r[name][key]!=value:raise ValueError('Conversion evidence differs')
   r[name][key]=copy.deepcopy(value)
 for answer in r['answer_evidence'].values():
  if any(cid not in r['cells'] for cid in answer['cell_ids']):raise ValueError('Conversion original cell missing')
 visits={(v['kobo_id'],v['month']) for v in r['visits']};identities={};catalogue={}
 for c in r['catalogue']:
  category=r['categories'][c['category']];key=(cold_conversion.family(category),c['brand_code'],c['brand'])
  identities.setdefault(key,set()).add(category)
 for item in source['brand_families']:
  key=tuple(item[k] for k in ['family','brand_code','brand'])
  if key in catalogue or set(item['categories_referenced'])!=identities.get(key):raise ValueError('Conversion family catalogue differs')
  catalogue[key]=item
 if set(catalogue)!=set(identities):raise ValueError('Conversion catalogue omitted identities')
 equipment={};rows={};source_nd={s['nd']['source_index']:s for s in r['stores']}
 for i,e in enumerate(source['equipment']):
  key=(e['kobo_id'],e['month'])
  if key not in visits or key in equipment:raise ValueError('Conversion equipment cohort differs')
  equipment[key]=(i,e)
 if set(equipment)!=visits:raise ValueError('Conversion equipment omitted visits')
 for s in source['stores']:
  key=tuple(s[k] for k in ['family','brand_code','brand']);visit=(s['kobo_id'],s['month']);identity=(*visit,*key)
  if key not in identities or visit not in visits or identity in rows:raise ValueError('Conversion store cohort differs')
  if set(s['categories_referenced'])!=identities[key] or s['equipment_index']!=equipment[visit][0]:raise ValueError('Conversion category or equipment reference differs')
  linked=[];categories=set()
  for index in s['presence_source_indices']:
   if index not in source_nd:raise ValueError('Conversion presence reference missing')
   item=source_nd[index];v=r['visits'][item['v']];c=r['catalogue'][item['c']]
   if (v['kobo_id'],v['month'],c['brand_code'],c['brand'])!=(*visit,s['brand_code'],s['brand']):raise ValueError('Conversion presence identity differs')
   category=r['categories'][c['category']]
   if category in categories:raise ValueError('Conversion presence repeated category')
   categories.add(category);linked.append((r['gates'][item['g']]['eligible'],item['nd']['presence']))
  if categories!=identities[key]:raise ValueError('Conversion presence category omitted')
  presence=1 if any(g is True and p==1 for g,p in linked) else None if any(g is None or g is True and p is None for g,p in linked) else 0
  operating=equipment[visit][1]['value'];eligible=False if presence==0 or operating==0 else True if presence==1 and operating==1 else None
  if presence!=s['presence'] or operating!=s['operating_equipment'] or eligible is not s['eligible']:raise ValueError('Conversion eligibility differs')
  if not s['answer_ids'] or any(a not in r['answer_evidence'] for a in s['answer_ids']):raise ValueError('Conversion answer missing')
  rows[identity]=s
 if set(rows)!={(*v,*key) for v in visits for key in identities}:raise ValueError('Conversion omitted brand/family visits')
 for name,kind in [('monthly','month'),('annual_observed_months','year_observed_months_pooled_store_months')]:
  seen=set()
  for item in source[name]:
   key=tuple(item[k] for k in ['family','brand_code','brand']);period=item['period'];identity=(period,*key)
   if identity in seen or key not in identities:raise ValueError('Conversion aggregate identity differs')
   seen.add(identity);group=[s for s in rows.values() if tuple(s[k] for k in ['family','brand_code','brand'])==key and (s['month'] if name=='monthly' else s['month'][:4])==period]
   if not group or len(item['store_rows'])!=len(group) or set(item['store_rows'])!={s['id'] for s in group}:raise ValueError('Conversion aggregate visits differ')
   expected=cold_conversion.aggregate(group,period,kind)
   if any(item.get(k)!=v for k,v in expected.items() if k!='store_rows'):raise ValueError('Conversion aggregate counts differ')
  periods={m if name=='monthly' else m[:4] for _,m in visits}
  if seen!={(p,*k) for p in periods for k in identities}:raise ValueError('Conversion aggregates omitted')
 r['conversion']=copy.deepcopy({k:v for k,v in source.items() if k not in ['cells','answer_evidence']});r['sources']['conversion']=copy.deepcopy(metadata)
 evidence={tuple(ids):i for i,ids in enumerate(r['evidence_sets'])}
 for name in ['stores','equipment','legacy_cold_inventories']:
  for row in r['conversion'][name]:
   ids=tuple(sorted(set(row.pop('answer_ids'))))
   if any(a not in r['answer_evidence'] for a in ids):raise ValueError('Conversion support missing')
   if ids not in evidence:evidence[ids]=len(r['evidence_sets']);r['evidence_sets'].append(list(ids))
   row['evidence_set']=evidence[ids]
 r['limits'].append('Conversion is one result per brand/family, not replicated as independent subcategory results. Category filters select references and retain the full family denominator.')
 return r
