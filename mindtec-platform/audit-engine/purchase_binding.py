"""Explicit source-scoped export-header aliases, separate from raw historical schemas."""
import copy,re
import engine


def validate(config,flat):
 if not isinstance(config,dict) or config.get('schema')!='mindtec-purchase-header-binding/1' or config.get('source_sha256')!=flat.source_sha256 or not isinstance(config.get('version'),str) or not config['version'].strip():raise ValueError('Versioned source-bound purchase alias required')
 if not config.get('forms') or not set(config['forms'])<=set(flat.bindings):raise ValueError('Purchase alias form scope differs')
 for rule in config['forms'].values():
  if rule.get('repeat')!='rep_empresa_compra' or rule.get('field')!='monto_compra_empresa' or not isinstance(rule.get('header_template'),str) or rule['header_template'].count('{index}')!=1 or '${empresa_label}' not in rule['header_template']:raise ValueError('Exact amount header and repeat identity required')
 if not config.get('observations') or any(not re.fullmatch('[0-9a-f]{64}',str(x.get('sha256',''))) for x in config['observations']):raise ValueError('Purchase alias observation evidence required')
 if {x.get('form') for x in config['observations']}!=set(config['forms']):raise ValueError('Purchase alias evidence form scope differs')


def resolve(flat,record,group,original,config):
 rule=config['forms'].get(record['form'])
 if rule is None:return original,None
 match=re.fullmatch(r'rep_empresa_compra\[([1-9]\d*)\]',group)
 if match is None:raise ValueError('Purchase alias repeat index invalid')
 header=rule['header_template'].replace('{index}',match[1]);indices=[i for i,h in enumerate(flat.headers) if h==header]
 if len(indices)!=1:raise ValueError('Unique exact purchase export header required')
 cell=flat.cell(record,indices[0]);route=group+'/monto_compra_empresa'
 if original['state']!='route_not_mapped':
  if original['state']=='observed' and cell['value']==original['value']:return original,None
  raise ValueError('Purchase alias cannot override an existing unresolved or conflicting route')
 recovered={'route':route,'state':'observed' if cell['value'] not in (None,'') else 'empty_observation','value':cell['value'] if cell['value'] not in (None,'') else None,'cells':[copy.deepcopy(cell)]}
 return recovered,{'version':config['version'],'original_route_state':original['state'],'method':'explicit_form_and_export_header_alias','header':header,'coordinate':cell['coordinate']}
