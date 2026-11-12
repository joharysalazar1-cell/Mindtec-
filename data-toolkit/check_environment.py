"""Read-only environment inventory; never installs missing modules."""
import importlib.metadata,importlib.util,json,pathlib,platform,sys
ROOT=pathlib.Path(__file__).resolve().parent
catalog=json.loads((ROOT/'catalog.json').read_text(encoding='utf-8'))
groups=set(sys.argv[1:] or ['core']);known={p['group'] for p in catalog['packages']}
if groups- known:raise SystemExit('Perfiles desconocidos: '+', '.join(sorted(groups-known)))
rows=[]
for package in catalog['packages']:
    if package['group'] not in groups:continue
    try:version=importlib.metadata.version(package['name'])
    except importlib.metadata.PackageNotFoundError:version=None
    rows.append({'package':package['name'],'expected':package['version'],'installed':version,'matches':version==package['version']})
print(json.dumps({'python':platform.python_version(),'platform':platform.platform(),'profiles':sorted(groups),'packages':rows},ensure_ascii=False,indent=2))
if any(not r['matches'] for r in rows):raise SystemExit(1)
