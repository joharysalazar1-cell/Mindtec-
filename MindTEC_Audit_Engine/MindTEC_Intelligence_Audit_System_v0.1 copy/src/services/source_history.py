"""Optional local storage of uploaded originals, outside version control."""
import hashlib
import json
from pathlib import Path
from uuid import uuid4
from datetime import datetime,timezone

DIRECTORY=Path(__file__).resolve().parents[2]/'data'/'staging'/'uploads'


def save_snapshot(record,metadata,directory=DIRECTORY):
    directory=Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    digest=hashlib.sha256(record['contenido']).hexdigest()
    blob=directory/(digest+'.bin')
    if not blob.exists():blob.write_bytes(record['contenido'])
    entry={k:v for k,v in record.items() if k!='contenido'}
    entry.update(sha256=digest,metadata=metadata,guardado_utc=datetime.now(timezone.utc).isoformat())
    filename=uuid4().hex+'.json'
    (directory/filename).write_text(json.dumps(entry,ensure_ascii=False,indent=2),encoding='utf-8')
    return filename


def list_snapshots(directory=DIRECTORY):
    entries=[]
    for path in sorted(Path(directory).glob('*.json')):
        try:
            entry=json.loads(path.read_text(encoding='utf-8'))
            entries.append((path.name,entry))
        except (ValueError,OSError):continue
    return entries


def restore_snapshot(filename,state,directory=DIRECTORY):
    if Path(filename).name!=filename or not filename.endswith('.json'):raise ValueError('Entrada inválida.')
    entry=json.loads((Path(directory)/filename).read_text(encoding='utf-8'))
    digest=entry['sha256']
    if len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('Hash inválido.')
    content=(Path(directory)/(digest+'.bin')).read_bytes()
    if hashlib.sha256(content).hexdigest()!=digest:raise ValueError('El archivo guardado no coincide con su hash.')
    metadata=entry.pop('metadata',{})
    entry['contenido']=content
    state.setdefault('archivos_cargados',{})[digest]=entry
    state.setdefault('source_metadata',{})[digest]=metadata
    return digest
