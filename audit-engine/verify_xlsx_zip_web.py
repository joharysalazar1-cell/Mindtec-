"""Compare every portable ZIP part with Python's independent ZIP extraction."""
import argparse,hashlib,io,json,pathlib,subprocess,zipfile

def verify(paths):
 root=pathlib.Path(__file__).resolve().parent;expected=[]
 for path in paths:
  with pathlib.Path(path).open('rb') as f:raw=f.read(25000001)
  if len(raw)>25000000:raise ValueError('Workbook exceeds compressed size limit')
  with zipfile.ZipFile(io.BytesIO(raw)) as z:
   entries=z.infolist()
   if len(entries)>10000 or sum(e.file_size for e in entries)>200000000 or any(e.file_size>100000000 for e in entries):raise ValueError('Workbook exceeds expansion limits')
   if len({e.filename for e in entries})!=len(entries):raise ValueError('Duplicate archive part')
   parts=[{'name':e.filename,'size':e.file_size,'sha256':hashlib.sha256(z.read(e)).hexdigest()} for e in entries]
  expected.append({'source_sha256':hashlib.sha256(raw).hexdigest(),'parts':parts})
 result=subprocess.run(['node',str(root/'verify-xlsx-zip.mjs'),*[str(pathlib.Path(p).resolve()) for p in paths]],cwd=root,capture_output=True,text=True,timeout=120)
 if result.returncode:raise ValueError('Portable ZIP reader rejected source: '+result.stderr[:2000])
 actual=json.loads(result.stdout)
 if len(actual)!=len(expected):raise ValueError('Archive count mismatch')
 for a,b in zip(actual,expected):
  if a.get('source_sha256')!=b['source_sha256'] or a.get('parts')!=b['parts']:raise ValueError('Portable ZIP bytes differ from Python extraction')
 return {'schema':'mindtec-xlsx-zip-parity/1','verified':True,'scope':'All uncompressed ZIP part bytes; worksheet cells not yet interpreted by the portable reader.','archives':actual}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('sources',nargs='+',type=pathlib.Path);p.add_argument('--output',type=pathlib.Path);a=p.parse_args();report=verify(a.sources)
 if a.output:a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,ensure_ascii=True,indent=2),encoding='utf-8')
 print(json.dumps({'verified':True,'archives':len(report['archives']),'parts':sum(len(x['parts']) for x in report['archives'])}))
