import pathlib,shutil,subprocess,unittest,tempfile
from test_invoice_pipeline import fixture_book
from verify_xlsx_zip_web import verify

class PortableZipTests(unittest.TestCase):
 @unittest.skipUnless(shutil.which('node'),'Node.js is required for portable ZIP checks')
 def test_portable_zip_adversarial_suite(self):
  root=pathlib.Path(__file__).resolve().parent
  result=subprocess.run(['node','--test','test-xlsx-zip.mjs'],cwd=root,capture_output=True,text=True,timeout=60)
  self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 @unittest.skipUnless(shutil.which('node'),'Node.js is required for portable ZIP checks')
 def test_independent_python_part_parity(self):
  with tempfile.TemporaryDirectory() as tmp:
   path=pathlib.Path(tmp)/'fixture.xlsx';fixture_book(path,53.33)
   report=verify([path]);self.assertTrue(report['verified']);self.assertEqual(len(report['archives'][0]['parts']),3)

if __name__=='__main__':unittest.main()
