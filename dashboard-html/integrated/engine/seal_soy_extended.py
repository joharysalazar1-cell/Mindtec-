import json
from pathlib import Path
import engine
base=Path('private/platform-recovered-2026-11-23');out=base/'soy24'
raw=(base/'extended-reviewed24.json').read_bytes();p=json.loads((base/'soc24u/integrated-result.json').read_text(encoding='utf-8'))
refs={'projection':((base/'soc24u/integrated-result.json').read_bytes(),'.json'),'confirmation':((out/'confirmation.json').read_bytes(),'.json'),'implementation':(engine.canonical({'code':Path('extended_reconstruction.py').read_text(encoding='utf-8')}).encode(),'.json')}
with engine.Engine(out/'custody') as e:
 a=e.record_result(raw,p['policy'],{'kind':'extended_reconstruction','version':'1.0.4-soy-confirmed','reference_sources':{k:engine.sha(v[0]) for k,v in refs.items()}},[],{'human_soy_faces':40},refs)
 receipt=dict(run_id=a['run_id'],snapshot_sha256=a['snapshot'],ledger_head=e.verify());(base/'extended-receipt24.json').write_text(engine.canonical(receipt),encoding='utf-8');print(engine.canonical(receipt))
