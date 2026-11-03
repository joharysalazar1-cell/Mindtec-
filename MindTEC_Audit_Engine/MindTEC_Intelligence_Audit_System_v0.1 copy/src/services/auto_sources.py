"""Read-only API ingestion. Credentials are resolved at runtime, never exported."""
import hashlib
import io
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # Never forward authentication to a redirect destination.
        return None


def configured_sources():
    path=ROOT/'config'/'sources.local.json'
    if path.exists():
        config=json.loads(path.read_text(encoding='utf-8-sig'))
        items=config.get('sources',[])
        if not isinstance(items,list):raise ValueError('sources debe ser una lista.')
        return items
    endpoint=os.environ.get('MINDTEC_API_URL','')
    if endpoint:
        return [dict(id='api_principal',name='Datos API',url_env='MINDTEC_API_URL',format=os.environ.get('MINDTEC_API_FORMAT','json'),records_path=os.environ.get('MINDTEC_API_RECORDS_PATH',''),key_env='MINDTEC_API_KEY',auth_header=os.environ.get('MINDTEC_API_HEADER','Authorization'),auth_prefix=os.environ.get('MINDTEC_API_PREFIX','Bearer '),refresh_seconds=300)]
    return []


def decode_table(body, kind, records_path=''):
    if kind=='csv':
        return pd.read_csv(io.BytesIO(body),sep=None,engine='python',dtype='string',encoding='utf-8-sig')
    if kind!='json':raise ValueError('Formato admitido: csv o json.')
    payload=json.loads(body)
    for part in records_path.split('.') if records_path else []:
        payload=payload[part]
    if not isinstance(payload,list) or any(not isinstance(row,dict) for row in payload):
        raise ValueError('La respuesta debe ser una lista de objetos; configura records_path si está anidada.')
    return pd.json_normalize(payload)


def fetch_source(config):
    url=os.environ.get(config.get('url_env',''),'') or config.get('url','')
    parsed=urlsplit(url)
    if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError('Configura un endpoint HTTPS sin credenciales en la URL.')
    headers={'Accept':'application/json, text/csv'}
    secret=os.environ.get(config.get('key_env','MINDTEC_API_KEY'),'')
    if not secret and config.get('requires_auth',True):
        raise ValueError('Falta la variable de entorno de la API key.')
    if secret:
        headers[config.get('auth_header','Authorization')]=config.get('auth_prefix','Bearer ')+secret
    request=Request(url,headers=headers,method='GET')
    with build_opener(NoRedirect()).open(request,timeout=20) as response:
        body=response.read(25*1024*1024+1)
    if len(body)>25*1024*1024:raise ValueError('Respuesta superior a 25 MB; configura un export acotado.')
    frame=decode_table(body,config.get('format','json'),config.get('records_path',''))
    # Retain returned values as a CSV snapshot; no business normalization or correction.
    content=frame.to_csv(index=False).encode('utf-8-sig')
    digest=hashlib.sha256(content).hexdigest()
    return digest,dict(nombre=config.get('name','API')+'.csv',extension='csv',contenido=content,tamano=len(content),hojas=None,origen='api',raw_sha256=hashlib.sha256(body).hexdigest(),filas=len(frame),actualizado_utc=pd.Timestamp.now(tz='UTC').isoformat())


def synchronize(state, force=False, fetcher=fetch_source):
    config=configured_sources()
    sources=state.setdefault('archivos_cargados',{})
    statuses=state.setdefault('api_status',{})
    changed=False
    for spec in config:
        ident=spec['id']
        status=statuses.setdefault(ident,{})
        now=time.time()
        interval=max(60,int(spec.get('refresh_seconds',300)))
        if not force and now-status.get('attempt',0)<interval:continue
        status['attempt']=now
        status['nombre']=spec.get('name',ident)
        try:
            digest,record=fetcher(spec)
            old=status.get('sha256')
            # A changed snapshot is retained. It may underpin an existing result.
            sources[digest]=record
            status.update(sha256=digest,estado='Actualizada',filas=record['filas'],actualizado_utc=record['actualizado_utc'])
            changed=changed or old!=digest
        except Exception as exc:
            # Do not display server bodies, URL parameters or exception strings containing secrets.
            status.update(estado='Error de sincronización; se conserva la última fuente disponible',tipo_error=type(exc).__name__)
    return config,changed
