"""Read a preserved Scan invoice workbook without changing cells or inferring keys."""
import argparse,hashlib,json,math,zipfile,xml.etree.ElementTree as E,io
from pathlib import Path

def workbook_cut(path,scope,raw=None):
 path=Path(path);ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
 if raw is None:
  with path.open('rb') as source:raw=source.read(25_000_001)
 if len(raw)>25_000_000:raise ValueError('Maximum workbook size: 25 MB')
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  if sum(i.file_size for i in z.infolist())>200_000_000 or any(i.file_size>100_000_000 for i in z.infolist()):raise ValueError('Workbook expansion exceeds bounded extraction limits')
  strings=[]
  if 'xl/sharedStrings.xml' in z.namelist():strings=[''.join(e.itertext()) for e in E.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',ns)]
  book=E.fromstring(z.read('xl/workbook.xml'));properties=book.find('m:workbookPr',ns)
  if properties is not None and properties.attrib.get('date1904') in ('1','true'):raise ValueError('Workbook uses an unsupported 1904 date system')
  rels={r.attrib['Id']:r.attrib['Target'].lstrip('/') for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
  sheets=[s for s in book.find('m:sheets',ns) if 'facturas' in s.attrib['name'].lower()]
  if len(sheets)!=1:raise ValueError('Expected one invoice-items worksheet; no invoice source may be substituted with survey tables')
  sheet=sheets[0];target=rels[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
  if not target.startswith('xl/'):target='xl/'+target
  rows=[];headers=None;columns=None;formula_cells=0
  for row in E.fromstring(z.read(target)).findall('.//m:sheetData/m:row',ns):
   cells={}
   for c in row:
    col=''.join(x for x in c.attrib['r'] if x.isalpha());typ=c.attrib.get('t');v=c.find('m:v',ns);inline=c.find('m:is',ns)
    if c.find('m:f',ns) is not None:formula_cells+=1
    value=v.text if v is not None else ''.join(inline.itertext()) if inline is not None else None
    if value is not None:
     if typ=='s':value=strings[int(value)]
     elif typ=='b':value=value=='1'
     elif typ not in ('inlineStr','str','e','d'):
      try:value=int(value) if not any(x in value.lower() for x in ['.','e']) else float(value)
      except ValueError:pass
    cells[col]=value
   if headers is None:
    columns=list(cells);headers=[cells[k] for k in columns]
   else:rows.append({'source_row':int(row.attrib['r']),'cells':[cells.get(k) for k in columns]})
 return {'schema':'mindtec-invoice-cut/1','headers':headers,'rows':rows,'scope':scope,'provenance':{'filename':path.name,'original_sha256':hashlib.sha256(raw).hexdigest(),'worksheet':sheet.attrib['name'],'date_system':'excel_1900','adapter_version':'invoice-xlsx/1.0.0','adapter_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'formula_cells_using_cached_values':formula_cells}}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--scope',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();cut=workbook_cut(a.source,json.loads(a.scope.read_text(encoding='utf-8')));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(cut,ensure_ascii=False,separators=(',',':'),allow_nan=False),encoding='utf-8');print(json.dumps({'rows':len(cut['rows']),'source_sha256':cut['provenance']['original_sha256']}))
