"""Convert a pip dry-run report to an explicitly platform-scoped hash lock."""
import hashlib,json,pathlib
ROOT=pathlib.Path(__file__).resolve().parent
report=json.loads((ROOT/'resolution-windows-py314.json').read_text(encoding='utf-8'))
packages=[];lines=['# Windows x64, CPython 3.14 only. Generated from pip dry-run report.','# Re-run resolution and review all changes before upgrading.']
for item in sorted(report['install'],key=lambda p:p['metadata']['name'].lower()):
    metadata=item['metadata'];sha=item['download_info']['archive_info']['hashes']['sha256']
    packages.append({'name':metadata['name'],'version':metadata['version'],'sha256':sha,'requested':item.get('requested',False)})
    lines.append(f'{metadata["name"]}=={metadata["version"]} --hash=sha256:{sha}')
(ROOT/'requirements/windows-py314.lock.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
(ROOT/'resolution-summary.json').write_text(json.dumps({'resolver':'pip --dry-run --ignore-installed --only-binary=:all:','environment':report['environment'],'packages':packages,'scope':'Dependency resolution only; installation and runtime tests are separate checks.','catalog_sha256':hashlib.sha256((ROOT/'catalog.json').read_bytes()).hexdigest()},indent=2),encoding='utf-8')
print(json.dumps({'resolved_packages':len(packages),'hash_lock':'requirements/windows-py314.lock.txt'}))
