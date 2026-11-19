"""Retain and replay technical quality indices from a verified invoice acceptance."""
import argparse
import base64
from pathlib import Path
import engine
import collection_watch
import invoice_adapter
import data_quality

ROOT=Path(__file__).resolve().parent
FILES=('data_quality.py','data_quality_run.py','invoice_core.py','invoice_adapter.py','engine.py','collection_watch.py')
LOADED={name:(ROOT/name).read_bytes() for name in FILES}
KIND='document_data_quality'


def calculate(raw,book,catalogue):
    cut=engine.load_json_bytes(raw)
    if engine.sha(book)!=cut.get('provenance',{}).get('original_sha256'):
        raise ValueError('Original workbook hash differs')
    rebuilt=invoice_adapter.workbook_cut('source.xlsx',cut['scope'],raw=book)
    if engine.canonical(rebuilt['headers'])!=engine.canonical(cut['headers']) or engine.canonical(rebuilt['rows'])!=engine.canonical(cut['rows']):
        raise ValueError('Original workbook cells differ')
    return data_quality.evaluate(cut,catalogue,source_raw=raw)


def verify(runtime,run_id=None):
    root=Path(runtime).resolve()
    if not (root/'audit.sqlite').is_file():raise ValueError('Existing quality custody required')
    with engine.Engine(root) as e:
        e.db.execute('BEGIN')
        try:
            e.verify();row=e.db.execute("SELECT * FROM runs WHERE json_extract(rules_json,'$.kind')=? AND (? IS NULL OR id=?) ORDER BY at DESC,id DESC LIMIT 1",(KIND,run_id,run_id)).fetchone()
            if row is None:raise ValueError('Accepted quality execution required')
            rules=engine.load_json_bytes(row['rules_json'].encode());refs=rules['reference_sources']
            if collection_watch.object_bytes(e,refs['implementation'])!=engine.code_bundle(LOADED):raise ValueError('Quality implementation differs')
            raw=collection_watch.object_bytes(e,refs['source_invoice_cut']);book=collection_watch.object_bytes(e,refs['original_workbook']);catalogue=None
            if 'dated_catalogue' in refs:
                envelope=engine.load_json_bytes(collection_watch.object_bytes(e,refs['dated_catalogue']));catalogue=base64.b64decode(envelope['content'],validate=True)
                if envelope.get('encoding')!='base64' or engine.sha(catalogue)!=envelope.get('original_sha256'):raise ValueError('Retained catalogue envelope differs')
            source=engine.load_json_bytes(collection_watch.object_bytes(e,refs['source_invoice_execution']))
            if source['snapshot_sha256']!=engine.sha(raw) or not source['original_workbook_verified']:raise ValueError('Invoice execution binding differs')
            result=calculate(raw,book,catalogue);result['source_invoice_run_id']=source['run_id']
            if collection_watch.object_bytes(e,row['snapshot_hash'])!=engine.canonical(result).encode() or row['findings_json']!=engine.canonical(result['findings']):raise ValueError('Quality result differs from replay')
            return {'run_id':row['id'],'snapshot_sha256':row['snapshot_hash'],'custody_verified':True,'findings':len(result['findings'])}
        finally:e.db.execute('ROLLBACK')


def execute(invoice_runtime,runtime,catalogue_path=None):
    source=Path(invoice_runtime).resolve();target=Path(runtime).resolve()
    if source.is_relative_to(target) or target.is_relative_to(source):raise ValueError('Separate invoice and quality custody required')
    if not (source/'audit.sqlite').is_file():raise ValueError('Existing accepted invoice source required')
    if catalogue_path is not None and Path(catalogue_path).resolve().is_relative_to(target):raise ValueError('Catalogue must remain outside custody')
    with engine.Engine(source) as e:
        e.db.execute('BEGIN')
        try:
            head=e.verify();row=e.db.execute("SELECT * FROM runs WHERE json_extract(rules_json,'$.kind')='invoice' ORDER BY at DESC,id DESC LIMIT 1").fetchone()
            if row is None:raise ValueError('Accepted invoice execution required')
            rules=engine.load_json_bytes(row['rules_json'].encode())
            if not rules.get('source_workbook_verified'):raise ValueError('Verified original workbook is required')
            raw=collection_watch.object_bytes(e,row['snapshot_hash']);book=collection_watch.object_bytes(e,rules['reference_sources']['current_workbook'])
            metadata={'run_id':row['id'],'snapshot_sha256':row['snapshot_hash'],'ledger_head':head,'original_workbook_verified':True}
        finally:e.db.execute('ROLLBACK')
    catalogue=collection_watch.bounded(Path(catalogue_path),10000000) if catalogue_path is not None else None
    result=calculate(raw,book,catalogue);result['source_invoice_run_id']=metadata['run_id']
    if any((ROOT/name).read_bytes()!=value for name,value in LOADED.items()):raise ValueError('Loaded quality dependency changed')
    references={'source_invoice_cut':(raw,'.json'),'source_invoice_execution':(engine.canonical(metadata).encode(),'.json'),'original_workbook':(book,'.xlsx'),'implementation':(engine.code_bundle(LOADED),'.json')}
    if catalogue is not None:references['dated_catalogue']=(engine.canonical({'encoding':'base64','original_sha256':engine.sha(catalogue),'content':base64.b64encode(catalogue).decode()}).encode(),'.json')
    rules={'kind':KIND,'version':data_quality.VERSION,'reference_sources':{name:engine.sha(value[0]) for name,value in references.items()}}
    total=next(p for p in result['periods'] if p['period']=='TOTAL');summary={'lines':total['lines'],'critical_null_rows':total['completeness']['rows_with_any_available_critical_null'],'findings':len(result['findings']),'network_delivery':False,'not_global_confidence':True}
    with engine.Engine(target) as e:r=e.record_result(engine.canonical(result).encode(),{'schema':'mindtec-quality-policy/1','version':data_quality.VERSION,'scope':'technical_controls_only'},rules,result['findings'],summary,references)
    return verify(target,r['run_id'])


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--invoice-runtime',type=Path);p.add_argument('--runtime',type=Path,required=True);p.add_argument('--catalogue',type=Path);p.add_argument('--verify',action='store_true');a=p.parse_args()
    if a.verify:print(engine.canonical(verify(a.runtime)))
    else:
        if a.invoice_runtime is None:p.error('--invoice-runtime is required')
        print(engine.canonical(execute(a.invoice_runtime,a.runtime,a.catalogue)))
