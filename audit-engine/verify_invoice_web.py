"""Cross-runtime parity of coverage and evidence for a specified pair of cuts."""
import argparse,json,subprocess
from pathlib import Path
from engine import canonical,sha,now
from invoice_core import evaluate

def verify(source,policy,reference=None):
 raw=Path(source).read_bytes();prior=Path(reference).read_bytes() if reference else None
 current=json.loads(raw);previous=json.loads(prior) if prior else None;policy_raw=Path(policy).read_bytes();p=json.loads(policy_raw)
 source_hash=sha(raw);reference_hash=sha(prior) if prior else None
 expected,coverage=evaluate(current,p,previous,source_hash,reference_hash)
 request={'cut':current,'reference':previous,'policy':p,'source_hash':source_hash,'reference_hash':reference_hash}
 result=subprocess.run(['node',str(Path(__file__).with_name('test-invoice-web.mjs'))],input=canonical(request),text=True,encoding='utf-8',capture_output=True,check=True)
 actual=json.loads(result.stdout)
 if actual['coverage']!=coverage:raise ValueError('Cross-runtime coverage mismatch')
 for field in ['fingerprint','issue_key']:
  if sorted(f[field] for f in expected)!=sorted(f[field] for f in actual['findings']):raise ValueError('Cross-runtime '+field+' mismatch')
 return {'verified_at':now(),'engine':actual['engine_version'],'implementation_sha256':sha(Path(__file__).with_name('invoice-web-core.mjs').read_bytes()),'source_sha256':source_hash,'reference_sha256':reference_hash,'policy_sha256':sha(policy_raw),'coverage':coverage,'exact_fingerprint_parity':True,'exact_issue_key_parity':True}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',required=True,type=Path);p.add_argument('--policy',required=True,type=Path);p.add_argument('--reference',type=Path);p.add_argument('--output',type=Path);a=p.parse_args();result=verify(a.source,a.policy,a.reference)
 if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(canonical(result),encoding='utf-8')
 print(canonical(result))
