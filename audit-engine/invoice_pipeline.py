"""Persist an invoice audit and its comparable reference in the evidence ledger."""
import argparse,json
from pathlib import Path
import engine,invoice_core,invoice_adapter
LOADED_SOURCES={Path(m.__file__).name:Path(m.__file__).read_bytes() for m in [invoice_core,invoice_adapter]}
LOADED_SOURCES['engine.py']=engine.IMPLEMENTATION_BYTES
LOADED_SOURCES[Path(__file__).name]=Path(__file__).read_bytes()
LOADED_HASHES={name:engine.sha(text) for name,text in LOADED_SOURCES.items()}

def execute(source,policy_path,runtime,reference=None,original_workbook=None,reference_workbook=None,*,source_bytes=None,policy_bytes=None,reference_bytes=None):
 if any(engine.sha(Path(__file__).with_name(name).read_bytes())!=hash_ for name,hash_ in LOADED_HASHES.items()):raise RuntimeError('Invoice implementation changed; restart before evaluating')
 raw=source_bytes if source_bytes is not None else Path(source).read_bytes();cut=invoice_core.validate_cut(engine.load_json_bytes(raw));policy=invoice_core.validate_policy(engine.load_json_bytes(policy_bytes if policy_bytes is not None else Path(policy_path).read_bytes()));prior_raw=reference_bytes if reference_bytes is not None else Path(reference).read_bytes() if reference else None;prior=invoice_core.validate_cut(engine.load_json_bytes(prior_raw)) if prior_raw else None
 refs={'implementation_bundle':(engine.code_bundle(LOADED_SOURCES),'.json')}
 if prior_raw:refs['previous_cut']=(prior_raw,'.json')
 for name,path,data in [('current_workbook',original_workbook,cut),('previous_workbook',reference_workbook,prior)]:
  if path:
   if data is None:raise ValueError('Workbook provided without its JSON cut')
   with Path(path).open('rb') as original:book=original.read(25_000_001)
   if len(book)>25_000_000:raise ValueError('Maximum original workbook size: 25 MB')
   if engine.sha(book)!=data.get('provenance',{}).get('original_sha256'):raise ValueError('Original workbook hash does not match cut provenance')
   rebuilt=invoice_adapter.workbook_cut(path,data['scope'],raw=book)
   if engine.canonical(rebuilt['headers'])!=engine.canonical(data['headers']) or engine.canonical(rebuilt['rows'])!=engine.canonical(data['rows']):raise ValueError('JSON cut cells differ from the preserved workbook')
   refs[name]=(book,'.xlsx')
 findings,coverage=invoice_core.evaluate(cut,policy,prior,engine.sha(raw),engine.sha(prior_raw) if prior_raw else None)
 rules={'engine_version':invoice_core.VERSION,'kind':'invoice','implementation_sha256':engine.sha(engine.canonical(LOADED_HASHES)),'rule_titles':invoice_core.TITLES,'reference_sources':{k:engine.sha(v[0]) for k,v in refs.items()},'source_workbook_verified':original_workbook is not None,'reference_workbook_verified':reference_workbook is not None}
 with engine.Engine(runtime) as e:result=e.record_result(raw,policy,rules,findings,coverage,refs)
 return {**result,'coverage':coverage}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--policy',type=Path,required=True);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--reference',type=Path);p.add_argument('--original-workbook',type=Path);p.add_argument('--reference-workbook',type=Path);a=p.parse_args();r=execute(a.source,a.policy,a.runtime,a.reference,a.original_workbook,a.reference_workbook);print(engine.canonical({k:v for k,v in r.items() if k!='findings'}))
