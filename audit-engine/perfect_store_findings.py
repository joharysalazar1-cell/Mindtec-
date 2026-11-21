"""Evidence-bound category contradictions; no fraud inference or automatic reviews."""
from pathlib import Path
import engine

VERSION='perfect-store-category-findings/1.0.0'
IMPLEMENTATION_BYTES=Path(__file__).read_bytes()

def evaluate(result):
 groups={}
 for check in result.get('eligibility_checks',[]):
  for signal in check['signals']:
   key=(check['kobo_id'],check['month'],check['parent_code'],signal)
   groups.setdefault(key,[]).append(check)
 findings=[]
 for (visit,month,parent,signal),checks in sorted(groups.items(),key=lambda x:engine.canonical(x[0])):
  support=sorted({a for c in checks for a in c['support']})
  if not support or any(a not in result['answer_evidence'] for a in support):raise ValueError('Contradiction requires retained answer support')
  cells=sorted({cid for a in support for cid in result['answer_evidence'][a]['cell_ids']})
  if not cells or any(c not in result['cells'] for c in cells):raise ValueError('Contradiction requires original cells')
  evidence={'source_sha256':result['source_sha256'],'kobo_id':visit,'month':month,'parent_code':parent,'categories':sorted({c['category'] for c in checks}),'answer_ids':support,'cell_ids':cells}
  f={'rule':signal,'rule_version':VERSION,'severity':'warning','title':'Respuestas de categorías requieren revisión','evidence':evidence,'explanation':'Las respuestas conservadas presentan una contradicción. Revisar preguntas y celdas originales; no demuestra fraude ni autoriza corregir la fuente o excluir la visita.','disposition':'needs_human_review'}
  f['fingerprint']=engine.sha(engine.canonical({'rule':signal,'version':VERSION,'evidence':evidence}));findings.append(f)
 return findings
