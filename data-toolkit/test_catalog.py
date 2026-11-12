import hashlib,json,pathlib,re,unittest
ROOT=pathlib.Path(__file__).resolve().parent

class CatalogTests(unittest.TestCase):
    def test_catalog_profiles_and_pins(self):
        data=json.loads((ROOT/'catalog.json').read_text(encoding='utf-8'));packages=data['packages']
        self.assertEqual(len(packages),51);self.assertEqual(len({p['name'].lower() for p in packages}),51)
        self.assertEqual(len({p['group'] for p in packages}),10)
        for p in packages:
            self.assertTrue(p['repository'].startswith('https://'))
            self.assertTrue(p['metadata_api'].startswith('https://pypi.org/pypi/'))
            text=(ROOT/'requirements'/f'{p["group"]}.txt').read_text(encoding='utf-8')
            self.assertIn(f'{p["requirement"]}=={p["version"]}',text)
    def test_resolution_provenance_and_hashes(self):
        summary=json.loads((ROOT/'resolution-summary.json').read_text(encoding='utf-8'))
        self.assertEqual(summary['catalog_sha256'],hashlib.sha256((ROOT/'catalog.json').read_bytes()).hexdigest())
        text=(ROOT/'requirements/windows-py314.lock.txt').read_text(encoding='utf-8')
        self.assertGreater(len(summary['packages']),51)
        for p in summary['packages']:
            self.assertRegex(p['sha256'],r'^[0-9a-f]{64}$')
            self.assertIn(f'{p["name"]}=={p["version"]} --hash=sha256:{p["sha256"]}',text)
    def test_resolved_direct_versions_match_catalog(self):
        data=json.loads((ROOT/'catalog.json').read_text(encoding='utf-8'))
        summary=json.loads((ROOT/'resolution-summary.json').read_text(encoding='utf-8'))
        normalize=lambda x:re.sub(r'[-_.]+','-',x).lower()
        resolved={normalize(p['name']):p['version'] for p in summary['packages']}
        for p in data['packages']:self.assertEqual(resolved[normalize(p['name'])],p['version'])

if __name__=='__main__':unittest.main()
