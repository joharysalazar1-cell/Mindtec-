"""Export evidence-bound review queues and append explicit local review decisions."""
import argparse
from pathlib import Path
import engine

STATES={'en_revision','dato_confirmado','correccion_solicitada','diferencia_explicada','sin_evidencia_suficiente'}
RESOLVED={'dato_confirmado','diferencia_explicada'}
LIMIT=200000

def existing(runtime):
 root=Path(runtime).resolve()
 if not (root/'audit.sqlite').is_file():raise ValueError('Existing verified audit custody required')
 return root

def run_record(e,run_id=None):
 row=e.db.execute('SELECT * FROM runs WHERE id=?',(run_id,)).fetchone() if run_id else e.db.execute('SELECT * FROM runs ORDER BY at DESC,id DESC LIMIT 1').fetchone()
 if not row:raise ValueError('Accepted audit execution not found')
 return row

def export_queue(runtime,output,run_id=None):
 root=existing(runtime);output=Path(output).resolve()
 if output.is_relative_to(root):raise ValueError('Export must be outside audit custody')
 with engine.Engine(root) as e:
  # One read transaction binds findings, reviews and ledger head to one snapshot.
  e.db.execute('BEGIN')
  try:
   head=e.verify();run=run_record(e,run_id);findings=engine.load_json_bytes(run['findings_json'].encode());reviews={}
   for row in e.db.execute('SELECT event_json FROM events ORDER BY seq'):
    event=engine.load_json_bytes(row[0].encode());p=event['payload']
    if event['action']=='finding.reviewed' and p['run_id']==run['id']:reviews[p['fingerprint']]={**p,'actor':event['actor'],'at':event['at']}
   rules=engine.load_json_bytes(run['rules_json'].encode())
   queue={'schema':'mindtec-review-queue/1','run_id':run['id'],'snapshot_sha256':run['snapshot_hash'],'ledger_head':head,'generated_at':engine.now(),'identity_assurance':'declared_local_identity_not_platform_authentication','reference_sources':rules.get('reference_sources',{}),'counts':{'findings':len(findings),'resolved_by_declared_review':sum(reviews.get(f['fingerprint'],{}).get('status') in RESOLVED for f in findings),'informational':sum(f['severity']=='info' for f in findings)},'items':[{'finding':f,'latest_review':reviews.get(f['fingerprint']),'requires_review':f['severity']!='info' and reviews.get(f['fingerprint'],{}).get('status') not in RESOLVED} for f in findings],'decision_contract':{'schema':'mindtec-local-review-decision/1','run_id':run['id'],'snapshot_sha256':run['snapshot_hash'],'expected_ledger_head':head,'fingerprint':'REPLACE_WITH_FINDING_FINGERPRINT','actor':'REPLACE_WITH_REVIEWER_NAME','status':'en_revision','note':'REPLACE_WITH_REASONED_REVIEW','evidence':'REPLACE_WITH_DOCUMENT_CELL_OR_REFERENCE'},'limits':['Export is a snapshot, not a live status.','A recorded decision does not independently authenticate its author or verify its conclusion.','Reviews append to history and never rewrite source records, rules or automated findings.','A decision for one run is not automatically transferred to later runs.']}
  finally:e.db.execute('ROLLBACK')
 # Exclusive creation prevents accidentally replacing a reviewed queue or draft.
 output.parent.mkdir(parents=True,exist_ok=True)
 with output.open('x',encoding='utf-8') as f:f.write(engine.canonical(queue))
 return {'output':str(output),'run_id':run['id'],'ledger_head':head,'counts':queue['counts']}

def apply_decision(runtime,decision_path):
 root=existing(runtime)
 with Path(decision_path).open('rb') as f:raw=f.read(LIMIT+1)
 if len(raw)>LIMIT:raise ValueError('Decision file exceeds size limit')
 d=engine.load_json_bytes(raw)
 required={'schema','run_id','snapshot_sha256','expected_ledger_head','fingerprint','actor','status','note','evidence'}
 if not isinstance(d,dict) or set(d)!=required or d['schema']!='mindtec-local-review-decision/1':raise ValueError('Exact local review decision contract required')
 if d['status'] not in STATES:raise ValueError('Unsupported review state')
 for field,maxlen in [('actor',300),('note',10000),('evidence',4000)]:
  value=d[field]
  if not isinstance(value,str) or not value.strip() or len(value)>maxlen or 'REPLACE_WITH_' in value:raise ValueError('Completed bounded reviewer, reason and evidence required')
 if len(d['note'].strip())<10:raise ValueError('Reason must contain at least ten characters')
 for field in ['run_id','snapshot_sha256','expected_ledger_head','fingerprint']:
  value=d[field]
  if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):raise ValueError('Exact SHA-256 binding required')
 with engine.Engine(root) as e:
  e.db.execute('BEGIN IMMEDIATE')
  try:
   head=e.verify()
   if head!=d['expected_ledger_head']:raise ValueError('Ledger advanced; export a fresh queue and reconsider the decision')
   run=run_record(e,d['run_id'])
   if run['snapshot_hash']!=d['snapshot_sha256']:raise ValueError('Decision refers to another source snapshot')
   if d['fingerprint'] not in {f['fingerprint'] for f in engine.load_json_bytes(run['findings_json'].encode())}:raise ValueError('Finding is not part of this run')
   artifact=e.store_object(raw);digest=engine.sha(raw)
   e.db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?)',(digest,str(artifact.relative_to(root))))
   payload={k:d[k].strip() if isinstance(d[k],str) else d[k] for k in ['run_id','fingerprint','status','note','evidence']}
   payload.update(decision_sha256=digest,source_snapshot_sha256=d['snapshot_sha256'],expected_ledger_head=head,identity_assurance='declared_local_identity_not_platform_authentication')
   e.append('finding.reviewed',payload,d['actor'].strip());new_head=e.verify();e.db.execute('COMMIT')
  except Exception:e.db.execute('ROLLBACK');raise
 return {'run_id':d['run_id'],'fingerprint':d['fingerprint'],'status':d['status'],'decision_sha256':digest,'ledger_head':new_head,'identity_assurance':'declared_local_identity_not_platform_authentication'}

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
 q=s.add_parser('export');q.add_argument('--runtime',required=True,type=Path);q.add_argument('--output',required=True,type=Path);q.add_argument('--run-id')
 a=s.add_parser('apply');a.add_argument('--runtime',required=True,type=Path);a.add_argument('--decision',required=True,type=Path)
 args=p.parse_args();print(engine.canonical(export_queue(args.runtime,args.output,args.run_id) if args.command=='export' else apply_decision(args.runtime,args.decision)))
