import io,json,tempfile,unittest,urllib.error,urllib.request
from pathlib import Path
from unittest.mock import Mock,patch
from engine import canonical,Engine
from scan_feed import config_file,download,Feed,FeedError,NoRedirect
from test_engine import POLICY,snapshot,visit

class Response(io.BytesIO):
 def __init__(self,raw,url,**headers):super().__init__(raw);self.url=url;self.status=200;self.headers={'Content-Type':'application/json',**headers}
 def geturl(self):return self.url

class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);p=self.root
  self.config={'schema':'mindtec-scan-feed/1','enabled':True,'url':'https://scan.test/api/exportar/normalizado.json','destination':str(p/'incoming.json'),'policy':str(p/'policy.json'),'audit_runtime':str(p/'audit'),'runtime':str(p/'feed'),'auth':{'kind':'bearer_env','token_env':'MINDTEC_SCAN_READ_TOKEN'},'timeout':5,'max_seconds':15,'max_bytes':100000,'interval':300};self.path=p/'config.json';self.write_config();(p/'policy.json').write_text(canonical(POLICY),encoding='utf-8');self.raw=canonical(snapshot(visit())).encode()
 def tearDown(self):self.temp.cleanup()
 def write_config(self):self.path.write_text(canonical(self.config),encoding='utf-8')
 def feed(self,fetch):return Feed(self.path,fetch=fetch,environ={'MINDTEC_SCAN_READ_TOKEN':'synthetic-secret-never-persist'})
 def test_success_is_archived_then_published_and_conditional_response_is_backed(self):
  fetch=Mock(side_effect=[{'not_modified':False,'raw':self.raw,'etag':'"v1"'},{'not_modified':True,'etag':'"v1"'}]);f=self.feed(fetch);first=f.poll();second=f.poll();self.assertEqual(first['status'],'healthy');self.assertTrue(second['unchanged']);self.assertEqual(first['run_id'],second['run_id']);self.assertEqual(fetch.call_args_list[1].args[1],'"v1"');self.assertEqual((self.root/'incoming.json').read_bytes(),self.raw)
  with Engine(self.root/'audit') as e:self.assertTrue(e.verify());self.assertEqual(e.db.execute('SELECT count(*) FROM runs').fetchone()[0],1)
  for p in self.root.rglob('*'):
   if p.is_file():self.assertNotIn(b'synthetic-secret-never-persist',p.read_bytes())
 def test_bad_or_ambiguous_json_never_replaces_accepted_source(self):
  for invalid in [b'{broken',b'{"total":1,"total":0,"envios":[]}',canonical({'total':1,'envios':[]}).encode()]:
   f=self.feed(Mock(side_effect=[{'not_modified':False,'raw':self.raw,'etag':None},{'not_modified':False,'raw':invalid,'etag':None}]));accepted=f.poll();self.assertEqual(accepted['status'],'healthy');result=f.poll();self.assertEqual(result['reason'],'invalid_scan_contract');self.assertEqual(result['last_accepted']['run_id'],accepted['run_id']);self.assertEqual((self.root/'incoming.json').read_bytes(),self.raw)
 def test_authentication_error_preserves_source_and_never_reads_error_body(self):
  (self.root/'incoming.json').write_bytes(b'prior source');body=io.BytesIO(b'sensitive error body');opener=Mock();opener.open.side_effect=urllib.error.HTTPError(self.config['url'],401,'Unauthorized',{},body)
  with self.assertRaises(FeedError) as caught:download(self.config,environ={'MINDTEC_SCAN_READ_TOKEN':'synthetic-secret'},opener=opener)
  self.assertEqual(caught.exception.reason,'authentication_required');self.assertTrue(body.closed);request=opener.open.call_args.args[0];self.assertEqual(request.get_method(),'GET');self.assertFalse(any(k.lower()=='cookie' for k,v in request.header_items()));self.assertEqual((self.root/'incoming.json').read_bytes(),b'prior source')
 def test_missing_credential_and_redirect_do_not_send_another_request(self):
  opener=Mock()
  with self.assertRaisesRegex(FeedError,'service_credential_missing'):download(self.config,environ={},opener=opener)
  opener.open.assert_not_called()
  with self.assertRaisesRegex(FeedError,'redirect_rejected'):NoRedirect().redirect_request(urllib.request.Request(self.config['url']),None,302,'',{},'https://other.test/')
 def test_limits_and_html_login_are_rejected(self):
  for response in [Response(b'{}',self.config['url'],**{'Content-Type':'text/html'}),Response(b'{}',self.config['url'],**{'Content-Length':'100001'}),Response(b'{}',self.config['url'],**{'Content-Length':'10'}),Response(b'{}',self.config['url'],**{'Content-Encoding':'gzip'})]:
   opener=Mock();opener.open.return_value=response
   with self.assertRaises(FeedError):download(self.config,environ={'MINDTEC_SCAN_READ_TOKEN':'secret'},opener=opener)
 def test_racing_destination_change_cannot_be_hidden_by_304(self):
  f=self.feed(Mock(return_value={'not_modified':False,'raw':self.raw,'etag':'"v1"'}));self.assertEqual(f.poll()['status'],'healthy')
  def changed(config,tag,**kwargs):(self.root/'incoming.json').write_bytes(b'changed');return {'not_modified':True}
  f.fetch=changed;self.assertEqual(f.poll()['reason'],'cached_source_changed_during_download')
 def test_disabled_feed_does_not_contact_source(self):
  self.config['enabled']=False;self.write_config();fetch=Mock();self.assertEqual(self.feed(fetch).poll()['status'],'disabled');fetch.assert_not_called();self.assertFalse((self.root/'audit').exists())
 def test_config_cannot_embed_a_secret_or_insecure_endpoint(self):
  for change in [{'url':'http://scan.test/'},{'url':'https://user:password@scan.test/'},{'url':'https://scan.test/?token=secret'},{'url':'https://scan.test:invalid/'},{'token':'embedded-secret'},{'destination':self.config['policy']},{'destination':str(self.root/'audit/objects/source.json')},{'runtime':self.config['audit_runtime']}]:
   original=dict(self.config);self.config.update(change);self.write_config()
   with self.assertRaises(FeedError):config_file(self.path)
   self.config=original
 def test_chunked_overflow_and_elapsed_limit_are_rejected(self):
  config=dict(self.config);config['max_bytes']=1;opener=Mock();opener.open.return_value=Response(b'{}',config['url'])
  with self.assertRaisesRegex(FeedError,'response_size_limit'):download(config,environ={'MINDTEC_SCAN_READ_TOKEN':'secret'},opener=opener)
  opener.open.return_value=Response(b'{}',config['url'])
  with self.assertRaisesRegex(FeedError,'download_time_limit'):download(config,environ={'MINDTEC_SCAN_READ_TOKEN':'secret'},opener=opener,clock=Mock(side_effect=[0,100]))
 def test_failure_transitions_are_persistent_and_do_not_duplicate_per_poll(self):
  f=self.feed(Mock(side_effect=FeedError('authentication_required',401)));self.assertEqual(f.poll()['status'],'degraded');f.poll()
  with Engine(self.root/'audit') as e:
   self.assertTrue(e.verify());self.assertEqual(e.db.execute('SELECT count(*) FROM runs').fetchone()[0],0);events=[json.loads(r[0]) for r in e.db.execute('SELECT event_json FROM events')];self.assertEqual(len(events),1);self.assertEqual(events[0]['action'],'feed.failed');self.assertEqual(events[0]['payload']['http_status'],401)
 def test_a_different_accepted_digest_cannot_be_published_as_the_download(self):
  target=self.root/'incoming.json';target.write_bytes(b'last valid source');f=self.feed(Mock(return_value={'not_modified':False,'raw':self.raw,'etag':None}))
  with patch('engine.Engine.ingest',return_value={'run_id':'other','snapshot':'other','reused':False}):result=f.poll()
  self.assertEqual(result['reason'],'accepted_source_digest_mismatch');self.assertEqual(target.read_bytes(),b'last valid source')

if __name__=='__main__':unittest.main()
