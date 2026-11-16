"""Admit a hash-bound, coherent pair of exports; never infer a full collection."""
import collections,re
from pathlib import Path
import engine,collection_adapter,collection_audit,collection_watch,flat_answers

VERSION='perfect-store-admission/1.0.0'
IMPLEMENTATION_BYTES=Path(__file__).read_bytes()
SOURCE_LIMITS={'detailed_workbook':25000000,'normalized_result_workbook':25000000,'historical_question_schema':20000000,'operational_configuration':4000000,'policy_file':100000,'identity_crosswalk':2000000}
COUNT_FIELDS=['expected_detail_counts','expected_normalized_counts','expected_eligible_counts']

def contract(raw,runtime,report_dir):
 value=engine.load_json_bytes(raw)
 required={'schema','version','label','sources',*COUNT_FIELDS}
 if not isinstance(value,dict) or set(value)!=required or value['schema']!='mindtec-perfect-store-admission/1':raise ValueError('Exact Perfect Store admission contract required')
 for field in ['version','label']:
  if not isinstance(value[field],str) or not value[field].strip() or len(value[field])>300:raise ValueError('Explicit bounded admission version and label required')
 months=None
 for field in COUNT_FIELDS:
  counts=value[field]
  if not isinstance(counts,dict) or not counts or any(not isinstance(k,str) or not re.fullmatch(r'\d{4}-(?:0[1-9]|1[0-2])',k) or isinstance(n,bool) or not isinstance(n,int) or n<=0 for k,n in counts.items()):raise ValueError('Explicit positive visit counts by YYYY-MM required')
  if months is not None and set(counts)!=months:raise ValueError('All admitted count scopes must have identical months')
  months=set(counts)
 if not isinstance(value['sources'],dict) or set(value['sources'])!=set(SOURCE_LIMITS):raise ValueError('All six named Perfect Store source roles required')
 paths=[]
 for role,ref in value['sources'].items():
  if not isinstance(ref,dict) or set(ref)!={'path','sha256'} or not isinstance(ref['path'],str) or not Path(ref['path']).is_absolute() or not isinstance(ref['sha256'],str) or not re.fullmatch('[0-9a-f]{64}',ref['sha256']):raise ValueError('Absolute source paths and exact SHA-256 required: '+role)
  p=Path(ref['path']).resolve();paths.append(p)
  if p.is_relative_to(Path(runtime).resolve()) or p.is_relative_to(Path(report_dir).resolve()):raise ValueError('Admitted inputs must be outside custody and reports')
 if len(set(paths))!=len(paths):raise ValueError('Each admission role requires a distinct source file')
 return value

def prepare(admission,raw_sources):
 """Use only captured source bytes, not subsequently mutable files."""
 if set(raw_sources)!=set(SOURCE_LIMITS):raise ValueError('Captured admission roles differ')
 for role,raw in raw_sources.items():
  if len(raw)>SOURCE_LIMITS[role] or engine.sha(raw)!=admission['sources'][role]['sha256']:raise ValueError('Admitted source fingerprint differs: '+role)
 policy=engine.validate_policy(engine.load_json_bytes(raw_sources['policy_file']));excluded={str(x['id']) for x in policy['exclusions']}
 config=engine.load_json_bytes(raw_sources['operational_configuration'])
 if not isinstance(config.get('version'),str) or not config['version'].strip():raise ValueError('Versioned operational configuration required')
 cross=collection_watch.mapping(raw_sources['identity_crosswalk'])
 normalized=collection_watch.validate(collection_adapter.workbook_tables('admitted-result.xlsx',raw_sources['normalized_result_workbook']))
 detailed=collection_adapter.workbook_tables('admitted-detail.xlsx',raw_sources['detailed_workbook'])
 flat=flat_answers.FlatAnswers(detailed,engine.load_json_bytes(raw_sources['historical_question_schema']))
 tables=collection_audit.tables(normalized);visits={};counts=collections.Counter()
 for row in tables['visits']['rows']:
  v=row['values'];internal=collection_audit.identifier(v['ID envío'])
  if not internal or internal not in cross or internal in visits:raise ValueError('Normalized visits require unique mapped internal IDs')
  visits[internal]={'id':cross[internal],'month':v['Mes']};counts[v['Mes']]+=1
 if dict(counts)!=admission['expected_normalized_counts']:raise ValueError('Normalized visit coverage differs from explicit admission')
 if dict(collections.Counter(r['month'] for r in flat.records))!=admission['expected_detail_counts']:raise ValueError('Detailed visit coverage differs from explicit admission')
 normal_cohort={(v['id'],v['month']) for v in visits.values() if v['id'] not in excluded};detail_cohort={(r['id'],r['month']) for r in flat.records if r['id'] not in excluded}
 if normal_cohort!=detail_cohort:raise ValueError('Eligible visit/month cohorts differ between exports')
 if dict(collections.Counter(month for _,month in detail_cohort))!=admission['expected_eligible_counts']:raise ValueError('Eligible visit coverage differs from explicit admission')
 catalog={}
 for row in tables['brands']['rows']:
  v=row['values'];internal=collection_audit.identifier(v.get('ID envío'));parent=visits.get(internal)
  if not parent or v.get('Mes')!=parent['month']:raise ValueError('Brand catalogue row has no compatible visit/month parent')
  key=(v.get('Subcategoría (código)'),v.get('Marca (código)'),v.get('Marca'))
  if any(not isinstance(x,str) or not x.strip() for x in key):raise ValueError('Incomplete brand catalogue identity')
  catalog[key]={'category':key[0],'brand_code':key[1],'brand':key[2]}
 if not catalog:raise ValueError('Empty brand catalogue cannot be admitted')
 return {'flat':flat,'catalog':list(catalog.values()),'policy':policy,'configuration':config,'detailed_book':detailed,'coverage':{'detail_counts':admission['expected_detail_counts'],'normalized_counts':admission['expected_normalized_counts'],'eligible_counts':admission['expected_eligible_counts'],'catalogue_entries':len(catalog)}}
