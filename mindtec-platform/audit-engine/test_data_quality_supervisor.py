import datetime as dt
import json
from pathlib import Path
import tempfile
import unittest
import supervisor
from test_supervisor import Child


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.invoice={'name':'invoice','kind':'invoice','source':str(self.root/'source.json'),'policy':str(self.root/'policy.json'),'runtime':str(self.root/'invoices'),'originals':str(self.root/'originals'),'interval':10}
        self.job={'name':'quality','kind':'data_quality','invoice_runtime':self.invoice['runtime'],'catalogue':str(self.root/'catalogue.csv'),'catalogue_sha256':'a'*64,'runtime':str(self.root/'quality'),'interval':60}

    def config(self,jobs=None):
        path=self.root/'config.json';path.write_text(json.dumps({'schema':'mindtec-supervisor/1','jobs':jobs or [self.invoice,self.job]}));return supervisor.config_file(path)

    def test_fixed_command_and_explicit_pin(self):
        self.config();args=supervisor.command(self.job);self.assertTrue(args[1].endswith('data_quality_watch.py'));self.assertIn('--catalogue-sha256',args);self.assertIn('a'*64,args);self.assertNotIn('--iterations',args)

    def test_requires_unique_configured_invoice_source_and_safe_interval(self):
        with self.assertRaises(ValueError):self.config([self.job])
        self.job['interval']=10
        with self.assertRaises(ValueError):self.config()

    def test_rejects_invalid_pin_and_nested_custody(self):
        self.job['catalogue_sha256']='bad'
        with self.assertRaises(ValueError):self.config()
        self.job['catalogue_sha256']='a'*64;self.job['runtime']=str(Path(self.invoice['runtime'])/'nested')
        with self.assertRaises(ValueError):self.config()

    def test_catalogue_cannot_belong_to_another_supervised_runtime(self):
        other={**self.invoice,'name':'other','runtime':str(self.root/'other')};self.job['catalogue']=str(self.root/'other'/'catalogue.csv')
        with self.assertRaises(ValueError):self.config([self.invoice,self.job,other])

    def test_health_ownership_and_custody_projection(self):
        now=dt.datetime.now(dt.timezone.utc);supervisor.atomic(Path(self.job['runtime'])/'health.json',{'pid':12,'checked_at':now.isoformat(),'status':'healthy','custody_verified':True,'finding_count':3,'network_delivery':False,'run_id':'accepted'})
        self.assertEqual(supervisor.health(self.job,13,now)['status'],'awaiting_owned_health');h=supervisor.health(self.job,12,now);self.assertTrue(h['custody_verified']);self.assertEqual(h['finding_count'],3)

    def test_waits_for_owned_invoice_health_before_launching(self):
        spawned=[]
        def spawn(*args,**kwargs):
            child=Child(101+len(spawned));spawned.append(child);return child
        owner=supervisor.Supervisor([self.invoice,self.job],self.root/'supervision',spawn=spawn);self.addCleanup(owner.close)
        first=owner.tick();self.assertEqual(len(spawned),1);self.assertEqual(first[1]['status'],'waiting_for_source')
        supervisor.atomic(Path(self.invoice['runtime'])/'invoice-health.json',{'pid':999,'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'healthy','run_id':'accepted'})
        owner.tick();self.assertEqual(len(spawned),1)
        supervisor.atomic(Path(self.invoice['runtime'])/'invoice-health.json',{'pid':101,'checked_at':dt.datetime.now(dt.timezone.utc).isoformat(),'status':'healthy','run_id':'accepted'})
        owner.tick();self.assertEqual(len(spawned),2)


if __name__=='__main__':unittest.main()
