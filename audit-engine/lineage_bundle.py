"""Project declared lineage inputs into bounded, deduplicated web dependencies.

This is a derived dependency artifact, not a replacement or byte-exact copy of
the original 80 MB Perfect Store detail. Parent hashes identify locally retained
files; a remote reader cannot verify those parent bytes from this projection.
"""
import argparse,json
from pathlib import Path
import engine

PARENT_NAMES={'kpis':'resultados_12_KPI.json','kpi_scope':'fuentes_y_alcance.json','perfect_store_details':'detalle_por_tienda.json','perfect_store_manifest':'manifiesto.json'}

def build(kpi_dir,perfect_store_dir):
 kp=Path(kpi_dir);ps=Path(perfect_store_dir)
 paths={'kpis':kp/'resultados_12_KPI.json','kpi_scope':kp/'fuentes_y_alcance.json','perfect_store_details':ps/'detalle_por_tienda.json','perfect_store_manifest':ps/'manifiesto.json'}
 raw={role:p.read_bytes() for role,p in paths.items()}
 return project(raw,{role:p.name for role,p in paths.items()})

def project(raw,names=None):
 """Use captured immutable parent bytes, without rereading mutable input files."""
 names=PARENT_NAMES if names is None else names
 if set(raw)!=set(PARENT_NAMES) or set(names)!=set(PARENT_NAMES):raise ValueError('Exactly four declared lineage parents required')
 data={role:engine.load_json_bytes(v) for role,v in raw.items()}
 sets=[];set_map={};answers=[];answer_map={};kpis=[];details=[]
 def intern(value,table,index):
  key=engine.canonical(value)
  if key not in index:index[key]=len(table);table.append(value)
  return index[key]
 for k in data['kpis']:
  projected={key:k.get(key) for key in ['id','mes','marca','categoria','indicador','publicado_original']}
  projected['operational_value']=k.get('operativo',{}).get('valor');projected['invoice_ref_set']=intern(k.get('operativo',{}).get('lineas_factura_relacionadas',[]),sets,set_map);kpis.append(projected)
 for row in data['perfect_store_details']:
  projected={key:row.get(key) for key in ['mes','categoria','marca','empresa','id_envio']};projected['components']=[]
  for c in row['componentes']:
   refs=[intern({'ruta':s['ruta'],'valor':s['valor']},answers,answer_map) for s in c.get('fuentes',[])]
   projected['components'].append({'name':c['componente'],'state':c['estado'],'value':c['valor'],'weight':c['peso'],'answer_refs':refs})
  details.append(projected)
 return {'schema':'mindtec-lineage-dependencies/1','parent_files':{role:{'filename':names[role],'sha256':engine.sha(raw[role])} for role in raw},'parent_bytes_verified_on_server':False,'projection_scope':'All fields consumed by lineage/1.0.0; descriptions and unrelated display fields are omitted. Original files remain separate.','kpi_scope':data['kpi_scope'],'perfect_store_manifest':data['perfect_store_manifest'],'invoice_ref_sets':sets,'answer_pool':answers,'kpis':kpis,'perfect_store':details}

def unpack(bundle):
 if bundle.get('schema')!='mindtec-lineage-dependencies/1':raise ValueError('Dependency bundle schema required')
 kpis=[];details=[]
 for row in bundle['kpis']:
  k={key:row[key] for key in ['id','mes','marca','categoria','indicador','publicado_original']};k['operativo']={'valor':row['operational_value'],'lineas_factura_relacionadas':bundle['invoice_ref_sets'][row['invoice_ref_set']]};kpis.append(k)
 for row in bundle['perfect_store']:
  r={key:row[key] for key in ['mes','categoria','marca','empresa','id_envio']};r['componentes']=[{'componente':c['name'],'estado':c['state'],'valor':c['value'],'peso':c['weight'],'fuentes':[bundle['answer_pool'][i] for i in c['answer_refs']]} for c in row['components']];details.append(r)
 return kpis,details

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--kpi-dir',type=Path,required=True);p.add_argument('--perfect-store-dir',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();b=build(a.kpi_dir,a.perfect_store_dir);a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(engine.canonical(b),encoding='utf-8');print(engine.canonical({'output':str(a.output.resolve()),'sha256':engine.file_hash(a.output),'bytes':a.output.stat().st_size,'kpis':len(b['kpis']),'perfect_store_rows':len(b['perfect_store']),'answer_pool':len(b['answer_pool']),'invoice_ref_sets':len(b['invoice_ref_sets'])}))
