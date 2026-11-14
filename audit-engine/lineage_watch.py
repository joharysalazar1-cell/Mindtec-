"""Refresh lineage only when accepted source runs or declared inputs change."""
import argparse,json,os,sqlite3,time
from pathlib import Path
import engine,kpi_lineage,lineage_report
from supervisor import exclusive,atomic

class Observer:
 def __init__(self,invoice_runtime,scan_runtime,kpi_dir,perfect_store_dir,runtime,report):
  self.invoice_runtime=Path(invoice_runtime);self.scan_runtime=Path(scan_runtime);self.kpi_dir=Path(kpi_dir);self.ps_dir=Path(perfect_store_dir);self.runtime=Path(runtime);self.report=Path(report);self.last_token=None;self.last_accepted=None
  self.code={Path(m.__file__).name:engine.file_hash(m.__file__) for m in [engine,kpi_lineage,lineage_report]};self.code[Path(__file__).name]=engine.file_hash(__file__)
 def token(self):
  for name,hash_ in self.code.items():
   if engine.file_hash(Path(__file__).with_name(name))!=hash_:raise RuntimeError('Implementation changed; restart lineage observer')
  ids=[]
  for runtime in [self.invoice_runtime,self.scan_runtime]:
   with sqlite3.connect((runtime/'audit.sqlite').resolve().as_uri()+'?mode=ro',uri=True) as db:
    row=db.execute('SELECT id FROM runs ORDER BY at DESC LIMIT 1').fetchone()
    if not row:raise ValueError('Upstream audit has no accepted run')
    ids.append(row[0])
  files=[self.kpi_dir/'resultados_12_KPI.json',self.kpi_dir/'fuentes_y_alcance.json',self.ps_dir/'detalle_por_tienda.json',self.ps_dir/'manifiesto.json']
  return engine.sha(engine.canonical({'runs':ids,'files':[engine.file_hash(p) for p in files],'implementation':self.code}))
 def poll(self):
  health={'pid':os.getpid(),'checked_at':engine.now(),'mode':'kpi_lineage_observer','last_accepted':self.last_accepted}
  try:
   token=self.token()
   if token!=self.last_token:
    result=kpi_lineage.execute(self.invoice_runtime,self.scan_runtime,self.kpi_dir,self.ps_dir,self.runtime)
    lineage_report.export_report(self.runtime,self.report)
    self.last_accepted={'run_id':result['run_id'],'snapshot':result['snapshot'],'summary':result['summary']};self.last_token=token
   # Verify custody even with unchanged inputs; a cached token is not proof of integrity.
   with engine.Engine(self.runtime) as e:head=e.verify()
   health.update(status='healthy',run_id=self.last_accepted['run_id'],last_accepted=self.last_accepted,ledger_head=head)
  except Exception as error:health.update(status='degraded',error_type=type(error).__name__,reason=str(error),last_accepted=self.last_accepted)
  atomic(self.runtime/'health.json',health);return health

def watch(observer,interval=10,iterations=None):
 if interval<1:raise ValueError('Minimum interval: one second')
 with exclusive(observer.runtime/'lineage-observer.lock'):
  count=0
  while True:
   result=observer.poll();count+=1
   if iterations is not None and count>=iterations:return result
   time.sleep(interval)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--invoice-runtime',required=True,type=Path);p.add_argument('--scan-runtime',required=True,type=Path);p.add_argument('--kpi-dir',required=True,type=Path);p.add_argument('--perfect-store-dir',required=True,type=Path);p.add_argument('--runtime',required=True,type=Path);p.add_argument('--report',required=True,type=Path);p.add_argument('--interval',type=float,default=10);p.add_argument('--iterations',type=int);a=p.parse_args();print(engine.canonical(watch(Observer(a.invoice_runtime,a.scan_runtime,a.kpi_dir,a.perfect_store_dir,a.runtime,a.report),a.interval,a.iterations)))
