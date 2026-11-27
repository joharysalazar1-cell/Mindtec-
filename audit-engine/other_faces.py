"""Resolve other-brand faces only under an explicit, source-bound export layout."""
import math,re
from pathlib import Path

VERSION='other-face-layout/1.0.0'
IMPLEMENTATION_BYTES=Path(__file__).read_bytes()

def number(a):
 v=a.get('value')
 return int(v) if a.get('state')=='observed' and type(v) in (int,float) and math.isfinite(v) and v>=0 and float(v).is_integer() else None

def resolve(flat,record,category,group,fields,rule):
 mode=rule['layout'];face=fields.get('caras_'+category,{});count=fields.get('n_otras_marcas_'+category,{});answers=[a for a in [face,count] if a];signals=[];consumed=set();rows=[]
 parent=re.fullmatch(r'rep_'+re.escape(category)+r'\[([1-9]\d*)\]',group)
 if not parent:raise ValueError('Explicit primary repetition required')
 outer=int(parent[1]);token=re.compile(r'(?:num_otra_marca|otra_marca_(?:sku|caras)|rep_otras_marcas)_'+re.escape(category)+r'(?![A-Za-z0-9_])')
 if mode=='direct_parent_faces':
  if count.get('state') not in (None,'route_not_mapped') or any(token.search(h) and record['row']['cells'][flat.columns[h]] not in (None,'') for h in flat.headers):signals.append('other_layout_conflict')
  value=number(face)
  if value is None:signals.append('other_parent_face_count_unresolved')
  return {'layout':mode,'complete':not signals,'faces':value if not signals else None,'known_faces':value,'rows':rows,'answers':answers,'consumed_columns':[],'signals':signals}
 if mode!='first_child_by_parent_index_then_explicit_paths':raise ValueError('Unsupported admitted other-face layout')
 n=number(count)
 if n is None:signals.append('other_child_count_unresolved')
 if face.get('state')=='observed':signals.append('unexpected_parent_faces_in_nested_branch')
 buckets={}
 for header in flat.headers:
  if not token.search(header):continue
  m=re.fullmatch(r'(.*?)\[([1-9]\d*)\](?: \((.+)\))?',header)
  if not m:continue
  base,index,path=m.group(1),int(m.group(2)),m.group(3);field=None
  if base=='num_otra_marca_'+category:field='ordinal'
  elif base=='Otra marca ${num_otra_marca_'+category+'}: ¿cuál es el nombre y SKU completo de la marca? (sabor y volumen)':field='name'
  elif re.fullmatch(r'¿Cuántas caras de \$\{otra_marca_sku_'+re.escape(category)+r'\} hay en la exhibición de .+\?',base):field='faces'
  if field is None:continue
  if path:
   match=re.fullmatch(re.escape(group)+r'/rep_otras_marcas_'+re.escape(category)+r'\[([1-9]\d*)\]/(num_otra_marca|otra_marca_sku|otra_marca_caras)_'+re.escape(category),path)
   if not match:continue
   expected={'ordinal':'num_otra_marca','name':'otra_marca_sku','faces':'otra_marca_caras'}[field]
   if match[2]!=expected:continue
   child=int(match[1]);method='explicit_full_nested_path'
  elif index==outer:child=1;method='admitted_first_child_by_parent_index'
  else:continue
  cell=flat.cell(record,flat.columns[header]);consumed.add(header);route=group+'/rep_otras_marcas_'+category+'['+str(child)+']/'+{'ordinal':'num_otra_marca_','name':'otra_marca_sku_','faces':'otra_marca_caras_'}[field]+category
  buckets.setdefault((child,field),[]).append((cell,route,method))
 active={i for (i,_),entries in buckets.items() if any(c['value'] not in (None,'') for c,_,_ in entries)}
 if n is not None and active!=set(range(1,n+1)):signals.append('other_child_enumeration_incomplete')
 for i in sorted(active):
  values={}
  for field in ['ordinal','name','faces']:
   entries=buckets.get((i,field),[]);filled=[c['value'] for c,_,_ in entries if c['value'] not in (None,'')]
   # No coercion or arbitrary alias selection: differing values are a conflict.
   distinct={(type(v).__name__,str(v)) for v in filled};state='observed' if len(distinct)==1 else 'conflicting_nested_columns' if filled else 'empty_observation'
   a={'route':entries[0][1] if entries else group+'/rep_otras_marcas_'+category+'['+str(i)+']/'+field,'state':state,'value':filled[0] if state=='observed' else None,'cells':[c for c,_,_ in entries],'binding_rule':sorted({method for _,_,method in entries})};answers.append(a);values[field]=a
  ordinal=number(values['ordinal']);faces=number(values['faces']);name=values['name']['value']
  if ordinal!=i or faces is None or not isinstance(name,str) or not name.strip():signals.append('other_child_observation_unresolved')
  rows.append({'index':i,'ordinal':ordinal,'name':name,'faces':faces})
 known=sum(r['faces'] for r in rows if r['faces'] is not None);signals=sorted(set(signals))
 return {'layout':mode,'complete':not signals,'faces':known if not signals else None,'known_faces':known,'rows':rows,'answers':answers,'consumed_columns':sorted(consumed),'signals':signals}
