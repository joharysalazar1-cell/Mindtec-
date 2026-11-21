"""Lossless reference and repeated-column indexing for the unified projection."""
import copy

def pack(original):
 r=copy.deepcopy(original);cell_ids=sorted(r['cells']);answer_ids=sorted(r['answer_evidence']);ci={k:i for i,k in enumerate(cell_ids)};ai={k:i for i,k in enumerate(answer_ids)};columns=sorted({c['column'] for c in r['cells'].values()});col={c:i for i,c in enumerate(columns)}
 cells=[]
 for key in cell_ids:
  c=r['cells'][key]
  if set(c)!={'source_sha256','sheet','source_row','coordinate','column','value','kobo_id'} or c['source_sha256']!=r['source_sha256'] or c['sheet']!='Envíos':raise ValueError('Unexpected original cell shape or source')
  cells.append([col[c['column']],c['source_row'],c['coordinate'],c['value'],c['kobo_id']])
 r['cells']=cells;r['answer_evidence']=[dict(r['answer_evidence'][k],cell_ids=[ci[c] for c in r['answer_evidence'][k]['cell_ids']]) for k in answer_ids];r['evidence_sets']=[[ai[k] for k in group] for group in r['evidence_sets']]
 for inv in r['inventories']:
  for obs in inv['unattributed']:obs['cell_id']=ci[obs['cell_id']]
 for wrapper in r.get('findings',[]):
  e=wrapper['finding']['evidence']
  for key,mapping in [('answer_ids',ai),('cell_ids',ci)]:
   if key in e:e[key]=[mapping[x] for x in e[key]]
  if 'cell_id' in e:e['cell_id']=ci[e['cell_id']]
 if 'conversion' in r:
  ids={s['id']:i for i,s in enumerate(r['conversion']['stores'])}
  if len(ids)!=len(r['conversion']['stores']):raise ValueError('Duplicate conversion store identity')
  for name in ['monthly','annual_observed_months']:
   for item in r['conversion'][name]:item['store_rows']=[ids[k] for k in item['store_rows']]
 return r,{'schema':'mindtec-integrated-reference-indices/1','cell_ids':cell_ids,'answer_ids':answer_ids,'columns':columns,'lossless':True}

def restore(packed,transport):
 r=copy.deepcopy(packed);cids=transport['cell_ids'];aids=transport['answer_ids'];columns=transport['columns'];r['cells']={key:{'source_sha256':r['source_sha256'],'sheet':'Envíos','source_row':c[1],'coordinate':c[2],'column':columns[c[0]],'value':c[3],'kobo_id':c[4]} for key,c in zip(cids,r['cells'],strict=True)};r['answer_evidence']={key:dict(a,cell_ids=[cids[i] for i in a['cell_ids']]) for key,a in zip(aids,r['answer_evidence'],strict=True)};r['evidence_sets']=[[aids[i] for i in group] for group in r['evidence_sets']]
 for inv in r['inventories']:
  for obs in inv['unattributed']:obs['cell_id']=cids[obs['cell_id']]
 for wrapper in r.get('findings',[]):
  e=wrapper['finding']['evidence']
  if 'answer_ids' in e:e['answer_ids']=[aids[i] for i in e['answer_ids']]
  if 'cell_ids' in e:e['cell_ids']=[cids[i] for i in e['cell_ids']]
  if 'cell_id' in e:e['cell_id']=cids[e['cell_id']]
 if 'conversion' in r:
  for name in ['monthly','annual_observed_months']:
   for item in r['conversion'][name]:item['store_rows']=[r['conversion']['stores'][i]['id'] for i in item['store_rows']]
 return r
