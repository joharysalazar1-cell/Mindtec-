import copy,datetime as dt,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from supervisor import config_file,command,health

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);p=self.root
  self.feed={'schema':'mindtec-scan-feed/1','enabled':True,'url':'https://scan.test/api/exportar/normalizado.json','destination':str(p/'incoming.json'),'policy':str(p/'policy.json'),'audit_runtime':str(p/'scan-runtime'),'runtime':str(p/'feed-runtime'),'auth':{'kind':'bearer_env','token_env':'MINDTEC_SCAN_READ_TOKEN'},'timeout':5,'max_seconds':15,'max_bytes':100000,'interval':300}
  self.feed_path=p/'feed.json';self.job={'name':'feed','kind':'feed','config':str(self.feed_path),'runtime':self.feed['runtime'],'interval':300};self.scan={'name':'scan','kind':'scan','source':self.feed['destination'],'policy':self.feed['policy'],'runtime':self.feed['audit_runtime'],'interval':10};self.config=p/'supervisor.json'
 def tearDown(self):self.tmp.cleanup()
 def write(self,jobs=None):
  self.feed_path.write_text(json.dumps(self.feed),encoding='utf-8');self.config.write_text(json.dumps({'schema':'mindtec-supervisor/1','jobs':jobs or [self.scan,self.job]}),encoding='utf-8')
 def test_enabled_feed_binds_without_reading_credentials_or_network(self):
  self.write()
  with patch('scan_feed.credential',side_effect=AssertionError('No credential read allowed')),patch('scan_feed.download',side_effect=AssertionError('No request allowed')):config_file(self.config)
  args=command(self.job);self.assertTrue(args[1].endswith('scan_feed.py'));self.assertEqual(args[2:],['--config',str(self.feed_path)])
 def test_disabled_feed_cannot_be_registered_as_active(self):
  self.feed['enabled']=False;self.write()
  with self.assertRaisesRegex(ValueError,'Disabled feed'):config_file(self.config)
 def test_miswired_destinations_and_policy_are_rejected(self):
  for field in ['source','policy','runtime']:
   changed=copy.deepcopy(self.scan);changed[field]=str(self.root/(field+'-other.json'));self.write([changed,self.job])
   with self.assertRaisesRegex(ValueError,'bind to one'):config_file(self.config)
 def test_health_poll_interval_matches_actual_download_schedule(self):
  for field,value in [('runtime',str(self.root/'other')),('interval',10)]:
   changed={**self.job,field:value};self.write([self.scan,changed])
   with self.assertRaisesRegex(ValueError,'runtime and interval'):config_file(self.config)
  p=Path(self.feed['runtime']);p.mkdir();(p/'health.json').write_text(json.dumps({'pid':123,'checked_at':(dt.datetime.now(dt.timezone.utc)-dt.timedelta(seconds=90)).isoformat(),'status':'degraded','reason':'authentication_required','http_status':401}),encoding='utf-8');state=health(self.job,123);self.assertEqual(state['reason'],'authentication_required');self.assertEqual(state['http_status'],401);self.assertNotIn('heartbeat_outside_window',state.values())
 def test_two_feeds_cannot_publish_to_same_scan_runtime(self):
  other=copy.deepcopy(self.feed);other['runtime']=str(self.root/'feed-other');other_path=self.root/'feed-other.json';other_path.write_text(json.dumps(other),encoding='utf-8');job={**self.job,'name':'feed-other','config':str(other_path),'runtime':other['runtime']};self.write([self.scan,self.job,job])
  with self.assertRaisesRegex(ValueError,'Only one feed'):config_file(self.config)

if __name__=='__main__':unittest.main()
