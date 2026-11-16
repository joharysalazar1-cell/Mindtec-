"""Export one retained comparison and its exact evidence for a manual private upload."""
import argparse,json
from pathlib import Path
import engine,scan_compare_watch

def export(scan_runtime,runtime,months,output):
 observer=scan_compare_watch.Observer(scan_runtime,runtime,months);prior=observer.prior()
 if not prior:raise ValueError('No accepted comparison or baseline')
 output=Path(output).resolve()
 if output.is_relative_to(observer.runtime) or output.is_relative_to(observer.source):raise ValueError('Export must be outside custody')
 with engine.Engine(observer.runtime) as e:
  e.db.execute('BEGIN')
  try:
   e.verify();row=e.db.execute('SELECT * FROM runs WHERE id=?',(prior['run_id'],)).fetchone();rules=json.loads(row['rules_json']);artifacts={}
   for role,digest in rules['reference_sources'].items():
    raw=scan_compare_watch.object_bytes(e,digest);artifacts[role]={'sha256':digest,'text':raw.decode('utf-8')}
   result=scan_compare_watch.object_bytes(e,row['snapshot_hash']).decode('utf-8')
   envelope={'schema':'mindtec-portable-scan-comparison/1','local_run_record_text':engine.canonical(dict(row)),'result_text':result,'artifacts':artifacts,'limits':{'local_ledger_included':False,'server_recalculation_claimed':False}}
   raw=engine.canonical(envelope).encode()
   if len(raw)>20000000:raise ValueError('Manual web package exceeds 20 MB; no truncated export')
  finally:e.db.execute('ROLLBACK')
 output.parent.mkdir(parents=True,exist_ok=True)
 with output.open('xb') as f:f.write(raw)
 return {'path':str(output),'sha256':engine.sha(raw),'bytes':len(raw),'local_run_id':prior['run_id'],'state':prior['state'],'uploaded':False}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--scan-runtime',required=True,type=Path);p.add_argument('--runtime',required=True,type=Path);p.add_argument('--months',required=True,nargs='+');p.add_argument('--output',required=True,type=Path);a=p.parse_args();print(engine.canonical(export(a.scan_runtime,a.runtime,a.months,a.output)))
