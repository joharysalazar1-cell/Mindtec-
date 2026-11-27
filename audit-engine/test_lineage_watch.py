import tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from lineage_watch import Observer

class Tests(unittest.TestCase):
 def test_unchanged_inputs_verify_custody_and_keep_last_valid_on_failure(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory);o=Observer(p,p,p,p,p/'runtime',p/'report.html');result={'run_id':'accepted','snapshot':'snapshot','summary':{'indicators':12}}
   with patch.object(o,'token',return_value='same'),patch('kpi_lineage.execute',return_value=result) as evaluate,patch('lineage_report.export_report'),patch('engine.Engine') as engine:
    engine.return_value.__enter__.return_value.verify.return_value='valid-head'
    self.assertEqual(o.poll()['status'],'healthy');self.assertEqual(o.poll()['status'],'healthy');self.assertEqual(evaluate.call_count,1)
    engine.return_value.__enter__.return_value.verify.side_effect=ValueError('Evidence integrity failed')
    health=o.poll();self.assertEqual(health['status'],'degraded');self.assertEqual(health['last_accepted']['run_id'],'accepted');self.assertEqual(evaluate.call_count,1)
 def test_bad_new_input_never_advances_last_accepted(self):
  with tempfile.TemporaryDirectory() as directory:
   p=Path(directory);o=Observer(p,p,p,p,p/'runtime',p/'report.html')
   with patch.object(o,'token',side_effect=['first','changed']),patch('kpi_lineage.execute',side_effect=[{'run_id':'accepted','snapshot':'s','summary':{}},ValueError('Different source cut')]),patch('lineage_report.export_report'),patch('engine.Engine') as engine:
    engine.return_value.__enter__.return_value.verify.return_value='valid-head'
    self.assertEqual(o.poll()['status'],'healthy');health=o.poll();self.assertEqual(health['status'],'degraded');self.assertEqual(health['last_accepted']['run_id'],'accepted');self.assertEqual(o.last_token,'first')

if __name__=='__main__':unittest.main()
