"""Compare retained Scan cuts without changing data, exclusions or human decisions."""
import argparse,collections,datetime,json,re
from pathlib import Path
import engine

VERSION='scan-cut-comparison/1.0.0'
MAX_FINDINGS=100000
IMPLEMENTATION_BYTES=Path(__file__).read_bytes()

def months_contract(months):
 if not isinstance(months,list) or not months or len(months)!=len(set(months)):raise ValueError('Explicit distinct months required')
 for month in months:
  if not isinstance(month,str) or not re.fullmatch(r'[0-9]{4}-(0[1-9]|1[0-2])',month):raise ValueError('Month must be YYYY-MM')
  datetime.date.fromisoformat(month+'-01')
 return sorted(months)

def index(parts):
 result=collections.defaultdict(list)
 for part_index,data in enumerate(parts):
  engine.validate_scan(data)
  for row_index,row in enumerate(data['envios']):
   form=row.get('formulario');date=row.get('fechaVisita')
   if not isinstance(form,str) or not form.strip():raise ValueError('Original form identity required; no cross-form inference')
   if not isinstance(date,str):raise ValueError('Visit date required for monthly comparison')
   try:month=datetime.datetime.fromisoformat(date.replace('Z','+00:00')).strftime('%Y-%m')
   except ValueError:raise ValueError('Valid visit date required for monthly comparison') from None
   result[(form,str(row['envioKobo']))].append({'part':part_index,'row':row_index,'month':month,'data':row})
 return result

def compare(previous,current,months):
 months=months_contract(months);before=index(previous);after=index(current);findings=[]
 summary={'months':{},'matched_records':0,'changed_records':0,'unchanged_records':0,'records_with_ambiguous_answers':0,'ambiguous_record_keys':0,'scope_complete_declared':False}
 for month in months:
  counts={side:sum(r['month']==month for rows in indexed.values() for r in rows) for side,indexed in [('previous',before),('current',after)]}
  # A missing month is a contract failure, never evidence that its visits vanished.
  if not all(counts.values()):raise ValueError('Requested month absent from one cut; no removal inference: '+month)
  summary['months'][month]=counts
 def emit(rule,key,evidence,explanation,severity='info'):
  if len(findings)>=MAX_FINDINGS:raise ValueError('Comparison finding limit exceeded; no truncated acceptance')
  evidence={'formulario':key[0],'record_id':key[1],**evidence}
  f={'rule':rule,'rule_version':'1','severity':severity,'title':rule.replace('_',' '),'evidence':evidence,'explanation':explanation,'disposition':'needs_human_review'}
  f['fingerprint']=engine.sha(engine.canonical({'rule':rule,'version':'1','evidence':evidence}));findings.append(f)
 def ref(row):return {k:row[k] for k in ['part','row','month']}
 for key in sorted(set(before)|set(after)):
  old=before.get(key,[]);new=after.get(key,[])
  if not any(r['month'] in months for r in old+new):continue
  if len(old)>1 or len(new)>1:
   summary['ambiguous_record_keys']+=1
   emit('ambiguous_record_key',key,{'previous_rows':[ref(r) for r in old],'current_rows':[ref(r) for r in new]},'No se empareja una identidad repetida ni se elige una fila automáticamente.','medium');continue
  if not old or not new:
   emit('record_added' if new else 'record_absent',key,{'previous_row':ref(old[0]) if old else None,'current_row':ref(new[0]) if new else None},'Presencia en los archivos comparados; una ausencia no demuestra borrado. Confirmar filtros, cobertura y corte.');continue
  a,b=old[0],new[0];summary['matched_records']+=1;start=len(findings)
  base={'previous_row':ref(a),'current_row':ref(b)}
  if (a['month'] in months)!=(b['month'] in months):
   emit('record_moves_across_scope',key,base,'La misma identidad cambió de mes de visita; no tratarla como alta o baja independiente.')
  left,right=a['data'],b['data']
  for field in sorted((set(left)|set(right))-{'respuestas'}):
   av={'present':field in left,'value':left.get(field)};bv={'present':field in right,'value':right.get(field)}
   if engine.canonical(av)!=engine.canonical(bv):emit('record_field_changed',key,{**base,'field':field,'previous':av,'current':bv},'Cambio de campo original entre cortes. Conservar ambos valores; no inferir el motivo o la autoría.')
  answers=[]
  for row in [left,right]:
   paths=collections.defaultdict(list)
   for n,answer in enumerate(row['respuestas']):paths[answer['ruta']].append({'answer_index':n,'answer':answer})
   answers.append(paths)
  for path in sorted(set(answers[0])|set(answers[1])):
   av,bv=answers[0].get(path,[]),answers[1].get(path,[])
   if len(av)>1 or len(bv)>1:
    emit('ambiguous_answer_path',key,{**base,'path':path,'previous':av,'current':bv},'Ruta repetida: no se selecciona el último valor ni se imputa una corrección.','medium');continue
   old_answer=av[0]['answer'] if av else None;new_answer=bv[0]['answer'] if bv else None
   if engine.canonical(old_answer)!=engine.canonical(new_answer):emit('answer_changed',key,{**base,'path':path,'previous':av,'current':bv},'Cambio de respuesta o de sus metadatos originales. Ausente, nulo, cero y texto se conservan como valores distintos.')
  emitted=findings[start:];ambiguous=any(f['rule']=='ambiguous_answer_path' for f in emitted)
  if ambiguous:summary['records_with_ambiguous_answers']+=1
  if any(f['rule']!='ambiguous_answer_path' for f in emitted):summary['changed_records']+=1
  elif not ambiguous:summary['unchanged_records']+=1
 summary['findings_by_rule']=dict(collections.Counter(f['rule'] for f in findings))
 return {'schema':'mindtec-scan-cut-comparison/1','version':VERSION,'months':months,'summary':summary,'findings':findings,'limits':['Partial exports cannot prove deletions.','Exact form and Kobo identity only; no store-based automatic deduplication.','All source rows are compared, including historically excluded rows.','No KPI, exclusion, review decision or source data is modified.','Changes are not evidence of fraud.']}

def run(previous_paths,current_paths,months,runtime):
 if not previous_paths or not current_paths or len(previous_paths)+len(current_paths)>24:raise ValueError('One or more inputs on each side; maximum 24 files')
 if Path(__file__).read_bytes()!=IMPLEMENTATION_BYTES or engine.sha(Path(engine.__file__).read_bytes())!=engine.IMPLEMENTATION_SHA:raise ValueError('Implementation changed; restart before comparison')
 root=Path(runtime).resolve();paths=[Path(p).resolve() for p in [*previous_paths,*current_paths]]
 if any(p.is_relative_to(root) for p in paths):raise ValueError('Input files must be outside comparison custody')
 refs={};parts={};total_bytes=0
 for side,side_paths in [('previous',previous_paths),('current',current_paths)]:
  parts[side]=[]
  for n,path in enumerate(side_paths):
   with Path(path).open('rb') as f:raw=f.read(60000001)
   if len(raw)>60000000:raise ValueError('Maximum source size: 60 MB')
   total_bytes+=len(raw)
   if total_bytes>200000000:raise ValueError('Maximum combined sources: 200 MB')
   parts[side].append(engine.load_json_bytes(raw));refs[f'{side}_{n}']=(raw,'.json')
 result=compare(parts['previous'],parts['current'],months)
 if Path(__file__).read_bytes()!=IMPLEMENTATION_BYTES:raise ValueError('Implementation changed during comparison')
 refs['implementation_bundle']=(engine.code_bundle({'engine.py':engine.IMPLEMENTATION_BYTES,'scan_compare.py':IMPLEMENTATION_BYTES}),'.json')
 policy={'schema':'mindtec-scan-comparison-policy/1','version':'1','months':months_contract(months),'no_source_mutation':True,'automatic_deduplication':False,'deletion_inference':False}
 rules={'kind':'scan_cut_comparison','version':VERSION,'reference_sources':{k:engine.sha(v[0]) for k,v in refs.items()}}
 with engine.Engine(root) as e:
  accepted=e.record_result(engine.canonical(result).encode(),policy,rules,result['findings'],result['summary'],refs);e.verify()
 return {'run_id':accepted['run_id'],'reused':accepted['reused'],'summary':result['summary']}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--previous',required=True,nargs='+',type=Path);p.add_argument('--current',required=True,nargs='+',type=Path);p.add_argument('--months',required=True,nargs='+');p.add_argument('--runtime',required=True,type=Path);a=p.parse_args();print(engine.canonical(run(a.previous,a.current,a.months,a.runtime)))
