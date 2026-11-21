"""Observe accepted local invoice runs and a pinned catalogue; no network or edits."""
import argparse
import base64
import os
from pathlib import Path
import re
import time
import engine
import collection_watch
import data_quality_run as runner
import supervisor
import windows_job

LOADED={**runner.LOADED,'data_quality_watch.py':Path(__file__).read_bytes(),'supervisor.py':supervisor.IMPLEMENTATION_BYTES,'windows_job.py':Path(windows_job.__file__).read_bytes()}


def source_execution(runtime):
    if not (Path(runtime)/'audit.sqlite').is_file():raise ValueError('Accepted invoice source is not ready')
    with engine.Engine(runtime) as e:
        e.db.execute('BEGIN')
        try:
            e.verify();row=e.db.execute("SELECT id,snapshot_hash FROM runs WHERE json_extract(rules_json,'$.kind')='invoice' ORDER BY at DESC,id DESC LIMIT 1").fetchone()
            if row is None:raise ValueError('Accepted invoice execution is not ready')
            return {'run_id':row['id'],'snapshot_sha256':row['snapshot_hash']}
        finally:e.db.execute('ROLLBACK')


class Observer:
    def __init__(self,invoice_runtime,catalogue,catalogue_sha256,runtime):
        self.source=Path(invoice_runtime).resolve();self.catalogue=Path(catalogue).resolve();self.runtime=Path(runtime).resolve();self.pin=catalogue_sha256;self.last_accepted=None
        if not re.fullmatch('[0-9a-f]{64}',str(self.pin)):raise ValueError('Explicit catalogue SHA-256 required')
        if self.source.is_relative_to(self.runtime) or self.runtime.is_relative_to(self.source) or self.catalogue.is_relative_to(self.runtime) or self.catalogue.is_relative_to(self.source):raise ValueError('Separate source/custody and external catalogue required')
        self.binding={'schema':'mindtec-quality-observer-binding/1','invoice_runtime':str(self.source),'catalogue':str(self.catalogue),'catalogue_sha256':self.pin}
        self.bundle=engine.code_bundle(LOADED)

    def unchanged_code(self):
        if any(Path(__file__).with_name(name).read_bytes()!=raw for name,raw in LOADED.items()):raise ValueError('Loaded quality observer dependency changed; restart required')

    def restore(self):
        with engine.Engine(self.runtime) as e:
            e.verify();row=e.db.execute("SELECT event_json FROM events WHERE json_extract(event_json,'$.action')='data_quality.observer.bound' ORDER BY seq LIMIT 1").fetchone()
            if row is None:e.append('data_quality.observer.bound',self.binding)
            elif engine.load_json_bytes(row[0].encode())['payload']!=self.binding:raise ValueError('Quality custody belongs to a different source or catalogue pin')
            row=e.db.execute("SELECT event_json FROM events WHERE json_extract(event_json,'$.action')='data_quality.observer.accepted' ORDER BY seq DESC LIMIT 1").fetchone()
            if row is not None:
                accepted=engine.load_json_bytes(row[0].encode())['payload'];verified=runner.verify(self.runtime,accepted['run_id'])
                if verified['snapshot_sha256']!=accepted['snapshot_sha256'] or accepted['catalogue_sha256']!=self.pin:raise ValueError('Accepted observer reference differs from custody')
                self.last_accepted=accepted

    def poll(self):
        h={'schema':'mindtec-quality-observer-health/1','pid':os.getpid(),'checked_at':engine.now(),'network_delivery':False,'custody_verified':False,'last_accepted':self.last_accepted};candidate=None
        try:
            self.unchanged_code();self.restore();candidate=collection_watch.bounded(self.catalogue,10000000)
            if engine.sha(candidate)!=self.pin:raise ValueError('Catalogue fingerprint changed; last valid result preserved')
            source=source_execution(self.source)
            reused=bool(self.last_accepted and self.last_accepted['source_invoice_execution']==source and self.last_accepted['observer_implementation_sha256']==engine.sha(self.bundle))
            accepted=runner.verify(self.runtime,self.last_accepted['run_id']) if reused else runner.execute(self.source,self.runtime,self.catalogue)
            if source_execution(self.source)!=source or engine.sha(collection_watch.bounded(self.catalogue,10000000))!=self.pin:raise ValueError('Source changed during quality calculation; no observer promotion')
            self.unchanged_code()
            if not reused:
                with engine.Engine(self.runtime) as e:
                    row=e.db.execute('SELECT snapshot_hash FROM runs WHERE id=?',(accepted['run_id'],)).fetchone();result=engine.load_json_bytes(collection_watch.object_bytes(e,row['snapshot_hash']))
                    if result['source_invoice_run_id']!=source['run_id'] or result['source_cut_sha256']!=source['snapshot_sha256'] or result['catalogue_sha256']!=self.pin:raise ValueError('Derived quality execution differs from selected source')
                    observer_bundle=e.store_object(self.bundle,'.json');e.db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?)',(engine.sha(self.bundle),str(observer_bundle.relative_to(e.root))))
                    self.last_accepted={**accepted,'source_invoice_execution':source,'catalogue_sha256':self.pin,'observer_implementation_sha256':engine.sha(self.bundle)};e.append('data_quality.observer.accepted',self.last_accepted)
            h.update(status='healthy',state='verified_unchanged' if reused else 'new_quality_result_accepted',custody_verified=True,run_id=self.last_accepted['run_id'],finding_count=self.last_accepted['findings'],last_accepted=self.last_accepted)
        except Exception as error:
            h.update(status='degraded',state='last_accepted_preserved' if self.last_accepted else 'no_quality_result_accepted',reason=str(error)[:1600],error_type=type(error).__name__,last_accepted=self.last_accepted)
            try:
                with engine.Engine(self.runtime) as e:
                    payload={'binding_sha256':engine.sha(engine.canonical(self.binding)),'reason':str(error)[:1600],'error_type':type(error).__name__,'last_accepted':self.last_accepted,'candidate_sha256':engine.sha(candidate) if candidate is not None else None}
                    if candidate is not None:
                        wrapped=engine.canonical({'encoding':'base64','original_sha256':engine.sha(candidate),'content':base64.b64encode(candidate).decode()}).encode();obj=e.store_object(wrapped,'.json');e.db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?)',(engine.sha(wrapped),str(obj.relative_to(e.root))));payload['candidate_object_sha256']=engine.sha(wrapped)
                    row=e.db.execute('SELECT event_json FROM events ORDER BY seq DESC LIMIT 1').fetchone()
                    if row is None or engine.load_json_bytes(row[0].encode()).get('payload')!=payload:e.append('data_quality.observer.rejected',payload)
            except Exception:h['failure_history_unverified']=True
        h['checked_at']=engine.now();supervisor.atomic(self.runtime/'health.json',h);return h


def watch(observer,interval=60,iterations=None):
    if isinstance(interval,bool) or not isinstance(interval,(int,float)) or not 60<=interval<=3600:raise ValueError('Quality interval must be 60 to 3600 seconds')
    if iterations is not None and (type(iterations)is not int or iterations<1):raise ValueError('Positive bounded iterations required')
    with supervisor.exclusive(observer.runtime/'quality-observer.lock'):
        h=None;count=0
        try:
            while True:
                h=observer.poll();count+=1
                if iterations is not None and count>=iterations:return h
                time.sleep(interval)
        finally:
            if h is not None:h.update(last_poll_status=h['status'],last_poll_state=h['state'],status='stopped',state='observer_stopped',observer_running=False,checked_at=engine.now());supervisor.atomic(observer.runtime/'health.json',h)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--invoice-runtime',required=True,type=Path);p.add_argument('--catalogue',required=True,type=Path);p.add_argument('--catalogue-sha256',required=True);p.add_argument('--runtime',required=True,type=Path);p.add_argument('--interval',type=float,default=60);p.add_argument('--iterations',type=int);a=p.parse_args();print(engine.canonical(watch(Observer(a.invoice_runtime,a.catalogue,a.catalogue_sha256,a.runtime),a.interval,a.iterations)))
