"""Read a preserved Scan invoice workbook without changing cells or inferring keys."""
import argparse,hashlib,json,math,zipfile,xml.etree.ElementTree as E,io,re
from pathlib import Path

class NoDoctype(E.TreeBuilder):
 def doctype(self,name,pubid,system):raise ValueError('XML document types and entities are not supported')

def xml_part(z,name):
 # ElementTree handles the declared XML encoding; the parser callback rejects
 # DTDs in UTF-8 and UTF-16 alike, before entity expansion can become evidence.
 return E.fromstring(z.read(name),parser=E.XMLParser(target=NoDoctype()))

def validate_archive(z):
 entries=z.infolist();names=[i.filename for i in entries]
 if len(entries)>10000 or len(set(names))!=len(names):raise ValueError('Duplicate ZIP entries or too many workbook parts')
 if sum(i.file_size for i in entries)>200_000_000 or any(i.file_size>100_000_000 for i in entries):raise ValueError('Workbook expansion exceeds bounded extraction limits')
 for i in entries:
  parts=i.filename.rstrip('/').split('/')
  if not parts or any(p in ('','.','..') for p in parts) or '\\' in i.filename or ':' in i.filename or i.orig_filename!=i.filename:raise ValueError('Unsafe workbook part path')
  if i.flag_bits&1 or i.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED):raise ValueError('Unsupported encrypted or compressed workbook part')

def workbook_cut(path,scope,raw=None):
 path=Path(path);ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
 if raw is None:
  with path.open('rb') as source:raw=source.read(25_000_001)
 if len(raw)>25_000_000:raise ValueError('Maximum workbook size: 25 MB')
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  validate_archive(z)
  strings=[]
  if 'xl/sharedStrings.xml' in z.namelist():strings=[''.join(e.itertext()) for e in xml_part(z,'xl/sharedStrings.xml').findall('m:si',ns)]
  book=xml_part(z,'xl/workbook.xml');properties=book.find('m:workbookPr',ns)
  if properties is not None and properties.attrib.get('date1904') in ('1','true'):raise ValueError('Workbook uses an unsupported 1904 date system')
  rels={}
  for r in xml_part(z,'xl/_rels/workbook.xml.rels'):
   if r.attrib['Id'] in rels:raise ValueError('Duplicate workbook relationship')
   if r.attrib.get('TargetMode')=='External':raise ValueError('External workbook relationships are not supported')
   rels[r.attrib['Id']]=r.attrib['Target'].lstrip('/')
  sheets=[s for s in book.find('m:sheets',ns) if 'facturas' in s.attrib['name'].lower()]
  if len(sheets)!=1:raise ValueError('Expected one invoice-items worksheet; no invoice source may be substituted with survey tables')
  sheet=sheets[0];target=rels[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
  if not target.startswith('xl/'):target='xl/'+target
  rows=[];headers=None;columns=None;formula_cells=0;previous_row=0
  for row in xml_part(z,target).findall('.//m:sheetData/m:row',ns):
   rn=row.attrib.get('r','')
   if not re.fullmatch(r'[1-9][0-9]{0,6}',rn) or not previous_row<int(rn)<=1048576:raise ValueError('Invalid, duplicate or unordered worksheet row')
   previous_row=int(rn)
   cells={}
   for c in row.findall('m:c',ns):
    match=re.fullmatch(r'([A-Z]{1,3})([1-9][0-9]{0,6})',c.attrib.get('r',''))
    if not match or int(match[2])!=int(rn):raise ValueError('Cell address does not match worksheet row')
    col=match[1];number=0
    for letter in col:number=number*26+ord(letter)-64
    if number>16384 or col in cells:raise ValueError('Invalid or duplicate worksheet cell')
    typ=c.attrib.get('t');v=c.find('m:v',ns);inline=c.find('m:is',ns)
    if c.find('m:f',ns) is not None:formula_cells+=1
    value=v.text if v is not None else ''.join(inline.itertext()) if inline is not None else None
    if value is not None:
     if typ=='s':
      if not re.fullmatch(r'[0-9]+',value) or int(value)>=len(strings):raise ValueError('Invalid shared string index')
      value=strings[int(value)]
     elif typ=='b':value=value=='1'
     elif typ not in ('inlineStr','str','e','d'):
      try:value=int(value) if not any(x in value.lower() for x in ['.','e']) else float(value)
      except ValueError:pass
      if isinstance(value,float) and not math.isfinite(value):raise ValueError('Nonfinite worksheet number')
    cells[col]=value
   if headers is None:
    columns=list(cells);headers=[cells[k] for k in columns]
   else:rows.append({'source_row':int(row.attrib['r']),'cells':[cells.get(k) for k in columns]})
 return {'schema':'mindtec-invoice-cut/1','headers':headers,'rows':rows,'scope':scope,'provenance':{'filename':path.name,'original_sha256':hashlib.sha256(raw).hexdigest(),'worksheet':sheet.attrib['name'],'date_system':'excel_1900','adapter_version':'invoice-xlsx/1.1.0','adapter_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'formula_cells_using_cached_values':formula_cells}}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--scope',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();cut=workbook_cut(a.source,json.loads(a.scope.read_text(encoding='utf-8')));a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(cut,ensure_ascii=False,separators=(',',':'),allow_nan=False),encoding='utf-8');print(json.dumps({'rows':len(cut['rows']),'source_sha256':cut['provenance']['original_sha256']}))
