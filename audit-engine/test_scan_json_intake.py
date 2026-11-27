import json,tempfile,unittest
from pathlib import Path
import engine
from test_engine import POLICY,snapshot,visit

class IntakeTests(unittest.TestCase):
 def test_duplicate_keys_are_rejected_at_every_level_including_unicode_alias(self):
  for raw in [b'{"total":0,"total":1,"envios":[]}',b'{"envios":[{"envioKobo":"a","envioKobo":"b","respuestas":[]}],"total":1}',b'{"a":{"valor":1,"valor":2}}',b'{"a":1,"\\u0061":2}']:
   with self.subTest(raw=raw),self.assertRaisesRegex(ValueError,'Duplicate JSON key'):engine.load_json_bytes(raw)
 def test_overflow_and_nonstandard_nonfinite_are_rejected_before_evaluation(self):
  for number in ['1e400','-1e400','NaN','Infinity','-Infinity']:
   with self.subTest(number=number),self.assertRaisesRegex(ValueError,'Non-finite JSON number'):engine.load_json_bytes(('{"a":'+number+'}').encode())
  self.assertEqual(engine.load_json_bytes(b'\xef\xbb\xbf{"a":1.25,"b":null,"c":false}'),{'a':1.25,'b':None,'c':False})
 def test_ambiguous_manual_input_is_quarantined_without_replacing_last_acceptance(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);source=root/'source.json';policy=root/'policy.json';runtime=root/'runtime'
   source.write_text(engine.canonical(snapshot(visit())),encoding='utf-8');policy.write_text(engine.canonical(POLICY),encoding='utf-8')
   good=engine.watch(source,policy,runtime,interval=1,stop_after=1)
   raw=b'{"total":1,"envios":[{"envioKobo":"a","respuestas":[],"codigoTienda":"original","codigoTienda":"replacement"}]}'
   source.write_bytes(raw);bad=engine.watch(source,policy,runtime,interval=1,stop_after=1)
   self.assertEqual(bad['status'],'degraded');self.assertEqual(bad['last_success']['snapshot'],good['last_success']['snapshot'])
   with engine.Engine(runtime) as e:
    self.assertEqual(e.db.execute('SELECT count(*) FROM runs').fetchone()[0],1)
    event=json.loads(e.db.execute('SELECT event_json FROM events ORDER BY seq DESC LIMIT 1').fetchone()[0]);self.assertEqual(event['action'],'ingestion.failed');self.assertEqual((runtime/event['payload']['object_path']).read_bytes(),raw);self.assertTrue(e.verify())

if __name__=='__main__':unittest.main()
