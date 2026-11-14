"""Verify portable lineage against the preserved full-file local result."""
import argparse,json,subprocess
from pathlib import Path
import engine,kpi_lineage,lineage_bundle

def verify(bundle_path,invoice_runtime,scan_runtime,lineage_runtime):
 raw=Path(bundle_path).read_bytes();bundle=engine.load_json_bytes(raw);invoice=kpi_lineage.accepted(invoice_runtime);scan=kpi_lineage.accepted(scan_runtime);lineage=kpi_lineage.accepted(lineage_runtime)
 expected=lineage['source'];engine_hashes={name:engine.file_hash(Path(__file__).with_name(name)) for name in ['lineage-web-core.mjs','lineage_bundle.py','verify_lineage_web.py']}
 if expected['invoice_run']['id']!=invoice['id'] or expected['scan_run']['id']!=scan['id']:raise ValueError('Preserved lineage does not belong to current source runs')
 kpis,details=lineage_bundle.unpack(bundle)
 projected_invoice=kpi_lineage.invoice_links(kpis,bundle['kpi_scope'],invoice['source'],invoice['findings'],invoice['source_hash']);projected_ps=kpi_lineage.perfect_store_links(details,bundle['perfect_store_manifest'],scan['source'],scan['source_hash'],scan['findings'])
 if projected_invoice!=expected['invoice_kpis'] or projected_ps!=expected['perfect_store']:raise ValueError('Projection changes lineage from full parent inputs')
 request={'bundle':bundle,'invoice':{'source':invoice['source'],'source_sha256':invoice['source_hash'],'findings':invoice['findings']},'scan':{'source':scan['source'],'source_sha256':scan['source_hash'],'findings':scan['findings']}}
 result=subprocess.run(['node',str(Path(__file__).with_name('test-lineage-web.mjs'))],input=engine.canonical(request),text=True,encoding='utf-8',capture_output=True,check=True)
 actual=json.loads(result.stdout)
 for field in ['invoice_kpis','perfect_store']:
  if actual[field]!=expected[field]:raise ValueError('Cross-runtime lineage mismatch: '+field)
 proof={'schema':'mindtec-lineage-parity/1','verified_at':engine.now(),'dependency_bundle_sha256':engine.sha(raw),'invoice_run':invoice['id'],'scan_run':scan['id'],'local_lineage_run':lineage['id'],'implementation_hashes':engine_hashes,'projection_preserves_all_lineage_results':True,'javascript_results_match_python':True,'summary':actual['summary'],'parent_bytes_verified_on_server':False}
 return proof

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--bundle',type=Path,required=True);p.add_argument('--invoice-runtime',type=Path,required=True);p.add_argument('--scan-runtime',type=Path,required=True);p.add_argument('--lineage-runtime',type=Path,required=True);p.add_argument('--output',type=Path);a=p.parse_args();proof=verify(a.bundle,a.invoice_runtime,a.scan_runtime,a.lineage_runtime)
 if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(engine.canonical(proof),encoding='utf-8')
 print(engine.canonical(proof))
