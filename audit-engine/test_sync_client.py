import copy,io,json,pathlib,tempfile,unittest,urllib.error
from unittest.mock import patch
import engine,sync_client
import test_sync_outbox as fixtures

class FakeSite:
 """Protocol failure fixtures; real Worker integration is checked separately."""
 def __init__(self):self.posts=[];self.objects={};self.runs={};self.failure=None;self.corrupt=None
 def post(self,path,raw,binary=False):
  self.posts.append(path)
  if self.failure and self.failure in path:raise sync_client.SyncError('transport_failure')
  id=engine.sha(path.encode()+raw);body={'id':id,'reused':False}
  if '/runs?' in path:self.runs[id]=engine.sha(raw)
  if path=='/sync/receipts':
   b=json.loads(raw);m=json.loads(b['manifest_text']);roles=['scan.source','scan.policy','invoice.source','invoice.policy','invoice.reference.current_workbook','web.lineage_dependencies']+(['invoice.reference.previous_cut','invoice.reference.previous_workbook'] if 'invoice.reference.previous_cut' in m['artifacts'] else []);mapping=copy.deepcopy(b['mappings']);mapping['workbooks'].sort()
   code=engine.canonical({'schema':'mindtec-web-code-bundle/1','files':{'sync-receipts.mjs':'// synthetic code'}}).encode()
   result={'schema':'mindtec-sync-receipt/1','state':'remote_inputs_verified','id':id,'package_sha256':b['manifest_sha256'],'local_package_run_id_declared':b['local_package_run_id'],'mappings':mapping,'verified_artifacts':{k:m['artifacts'][k]['sha256'] for k in roles},'unverified_local_artifacts':sorted(set(m['artifacts'])-set(roles)),'local_ledger_verified':False,'parent_bytes_verified_on_server':False,'numeric_parity_claimed':False,'implementation_sha256':engine.sha(code),'remote_runs':{k:{'id':mapping[k],'source_sha256':self.runs[mapping[k]],'findings_sha256':engine.sha('findings'),'implementation_sha256':engine.sha('code')} for k in ['scan','invoice','lineage']}}
   if self.corrupt=='package':result['package_sha256']='0'*64
   if self.corrupt=='scope':result['local_ledger_verified']=True
   result_raw=engine.canonical(result).encode();base='/sync/receipts/'+id
   self.objects.update({base+'/result':result_raw,base+'/manifest':b['manifest_text'].encode(),base+'/request':raw,base+'/code':code});body['receipt']={'id':id,'result_sha256':engine.sha(result_raw)}
  return body,engine.canonical(body).encode()
 def get(self,path,expected=None,binary=False,limit=30000000):
  if self.failure and self.failure in path:raise sync_client.SyncError('transport_failure')
  raw=self.objects[path]
  if self.corrupt=='manifest' and path.endswith('/manifest'):raw=b'{}'
  if expected:sync_client.require(engine.sha(raw)==expected,'remote_readback_differs_from_acceptance')
  return raw

class ClientTests(unittest.TestCase):
 def setUp(self):
  self.f=fixtures.OutboxTests();self.f.setUp();self.addCleanup(self.f.tearDown);self.f.prepare();self.path=self.f.root/'client.json';self.c={'schema':'mindtec-sync-client/1','enabled':True,'origin':'https://audit.example.org','project_id':'appgprj_fixture','outbox_runtime':str(self.f.outbox),'runtime':str(self.f.root/'delivery'),'token_env':'MINDTEC_SITE_SERVICE_TOKEN','timeout':10,'max_seconds':30};self.save();self.site=FakeSite()
 def save(self):self.path.write_text(engine.canonical(self.c),encoding='utf-8')
 def client(self):return sync_client.Client(self.path,transport=self.site)
 def count(self):
  with engine.Engine(self.c['runtime']) as e:return e.db.execute('SELECT count(*) FROM runs').fetchone()[0]
 def test_only_readback_creates_durable_acceptance_and_repeat_only_rechecks(self):
  first=self.client().run();self.assertEqual(first['state'],'delivered_verified');self.assertEqual(self.count(),1);posts=len(self.site.posts)
  second=self.client().run();self.assertTrue(second['reused']);self.assertEqual(second['run_id'],first['run_id']);self.assertEqual(len(self.site.posts),posts)
  with engine.Engine(self.c['runtime']) as e:self.assertTrue(e.verify())
 def test_partial_network_failure_keeps_unconfirmed_then_recovers(self):
  self.site.failure='/lineage/runs';bad=self.client().run();self.assertEqual(bad['status'],'degraded');self.assertEqual(self.count(),0)
  self.site.failure=None;good=self.client().run();self.assertEqual(good['state'],'delivered_verified');self.assertEqual(self.count(),1)
 def test_incorrect_package_overstated_scope_or_bad_readback_never_accepted(self):
  for mode in ['package','scope','manifest']:
   with self.subTest(mode=mode):self.site.corrupt=mode;self.assertEqual(self.client().run()['status'],'degraded');self.assertEqual(self.count(),0)
 def test_missing_remote_receipt_on_repeat_does_not_create_new_acceptance(self):
  good=self.client().run();self.site.failure='/result';bad=self.client().run();self.assertEqual(bad['status'],'degraded');self.assertEqual(self.count(),1)
 def test_wrong_target_or_corrupt_source_stops_before_any_post(self):
  self.c['origin']='https://other.example.org';self.save();self.assertEqual(self.client().run()['status'],'degraded');self.assertEqual(self.site.posts,[])
  self.c['origin']='https://audit.example.org';self.save();_,m=self.f.accepted();hash_=m['artifacts']['invoice.reference.current_workbook']['sha256'];(self.f.outbox/'objects'/(hash_+'.xlsx')).write_bytes(b'changed');self.assertEqual(self.client().run()['status'],'degraded');self.assertEqual(self.site.posts,[])
 def test_disabled_needs_no_credential_and_makes_no_request(self):
  self.c['enabled']=False;self.save()
  with patch.dict('os.environ',{},clear=True):result=sync_client.Client(self.path).run()
  self.assertEqual(result['status'],'disabled');self.assertEqual(self.site.posts,[])
 def test_configuration_cannot_contain_secrets_or_overlap_custody(self):
  self.c['token']='do-not-store';self.save()
  with self.assertRaises(sync_client.SyncError):self.client()
  del self.c['token'];self.c['runtime']=str(self.f.outbox/'nested');self.save()
  with self.assertRaises(sync_client.SyncError):self.client()
 def test_failed_transition_is_deduplicated_and_contains_no_response_body(self):
  self.site.failure='/audit/policies';self.client().run();self.client().run()
  with engine.Engine(self.c['runtime']) as e:
   events=[json.loads(r[0]) for r in e.db.execute('SELECT event_json FROM events')];self.assertEqual(len(events),1);self.assertNotIn('token',engine.canonical(events));self.assertEqual(events[0]['action'],'sync.delivery.failed')
 def test_comparable_cut_sends_both_originals_and_explicit_reference(self):
  import invoice_pipeline
  from invoice_adapter import workbook_cut
  from test_invoice_pipeline import fixture_book
  book=self.f.root/'old.xlsx';fixture_book(book,52.33);source=self.f.root/'old.json';self.f.write(source,workbook_cut(book,self.f.cut['scope']))
  invoice_pipeline.execute(self.f.source,self.f.policy,self.f.invoice,source,self.f.book,book);self.f.make_lineage();self.f.prepare()
  result=self.client().run();self.assertEqual(result['state'],'delivered_verified');self.assertTrue(any('&reference=' in p for p in self.site.posts));self.assertTrue(any('side=reference' in p for p in self.site.posts))

class Response:
 def __init__(self,raw=b'{}',url='https://audit.example.org/api/service-sync/audit/policies',headers=None):self.body=io.BytesIO(raw);self.status=200;self.url=url;self.headers={'Content-Type':'application/json','X-Content-SHA256':engine.sha(raw),**(headers or {})}
 def __enter__(self):return self
 def __exit__(self,*args):self.body.close()
 def geturl(self):return self.url
 def read(self,n):return self.body.read(n)
class Opener:
 def __init__(self,response):self.response=response;self.request=None
 def open(self,request,timeout):self.request=request;return self.response
class TransportTests(unittest.TestCase):
 def config(self):return {'origin':'https://audit.example.org','timeout':10,'max_seconds':30}
 def test_credential_only_goes_to_bound_site_headers_without_cookies(self):
  opener=Opener(Response());t=sync_client.Transport(self.config(),'synthetic-service-token',opener=opener);raw,hash_=t.exchange('POST','/api/service-sync/audit/policies',b'{}');self.assertEqual(raw,b'{}');self.assertEqual(opener.request.get_header('Oai-sites-authorization'),'Bearer synthetic-service-token');self.assertIsNone(opener.request.get_header('Cookie'))
  with self.assertRaises(sync_client.SyncError):t.exchange('POST','https://other.local/api',b'{}')
 def test_wrong_origin_excess_truncation_or_encoding_rejected(self):
  for response in [Response(url='https://other.local/'),Response(headers={'Content-Length':'9999999999'}),Response(headers={'Content-Length':'5'}),Response(headers={'Content-Encoding':'gzip'})]:
   with self.subTest(response=response),self.assertRaises(sync_client.SyncError):sync_client.Transport(self.config(),'synthetic',opener=Opener(response)).exchange('POST','/api/service-sync/audit/policies',b'{}')
 def test_redirect_is_closed_and_not_followed(self):
  stream=io.BytesIO(b'not-read')
  with self.assertRaises(sync_client.SyncError):sync_client.NoRedirect().redirect_request(None,stream,302,'redirect',{},'https://other.local')
  self.assertTrue(stream.closed)
 def test_ambiguous_json_rejected(self):
  for raw in [b'{"id":1,"id":2}',b'{"value":NaN}',b'<login/>']:
   with self.assertRaises(sync_client.SyncError):sync_client.parsed(raw)
 def test_missing_or_incorrect_readback_header_is_not_verified(self):
  for header in [None,'0'*64]:
   opener=Opener(Response(headers={'X-Content-SHA256':header}));transport=sync_client.Transport(self.config(),'synthetic',opener=opener)
   with self.assertRaises(sync_client.SyncError):transport.get('/audit/policies')
 def test_http_failure_does_not_read_or_expose_error_body(self):
  error=urllib.error.HTTPError('https://audit.example.org/api/service-sync/audit/policies',401,'Denied',{},io.BytesIO(b'sensitive error body'))
  with patch.object(Opener,'open',side_effect=error):
   with self.assertRaises(sync_client.SyncError) as raised:sync_client.Transport(self.config(),'synthetic',opener=Opener(None)).exchange('POST','/api/service-sync/audit/policies',b'{}')
  self.assertEqual(raised.exception.reason,'authentication_required');self.assertNotIn('sensitive',str(raised.exception))

if __name__=='__main__':unittest.main()
