"""Read normalized Scan result worksheets, preserving cell coordinates and types."""
import hashlib,io,math,re,zipfile
from pathlib import Path
from invoice_adapter import validate_archive,xml_part

VERSION='scan-result-xlsx/1.0.0'
IMPLEMENTATION_BYTES=Path(__file__).read_bytes()
NS={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def workbook_tables(path,raw=None):
 path=Path(path)
 if raw is None:
  with path.open('rb') as f:raw=f.read(25000001)
 if len(raw)>25000000:raise ValueError('Maximum result workbook size: 25 MB')
 with zipfile.ZipFile(io.BytesIO(raw)) as z:
  validate_archive(z);strings=[]
  if 'xl/sharedStrings.xml' in z.namelist():strings=[''.join(t.text or '' for t in si.iter('{'+NS['m']+'}t')) for si in xml_part(z,'xl/sharedStrings.xml').findall('m:si',NS)]
  book=xml_part(z,'xl/workbook.xml');props=book.find('m:workbookPr',NS);date1904=props is not None and props.attrib.get('date1904') in ('1','true');rels={}
  for rel in xml_part(z,'xl/_rels/workbook.xml.rels'):
   if rel.attrib.get('TargetMode')=='External' or rel.attrib['Id'] in rels:raise ValueError('External or duplicate workbook relationship')
   target=rel.attrib['Target'].lstrip('/')
   if '..' in target.split('/'):raise ValueError('Unsafe worksheet target')
   rels[rel.attrib['Id']]=target if target.startswith('xl/') else 'xl/'+target
  tables=[]
  for sheet in book.find('m:sheets',NS):
   target=rels[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']];rows=[];previous=0;formulas=0;maxcol=0
   for row in xml_part(z,target).findall('m:sheetData/m:row',NS):
    number=int(row.attrib['r'])
    if not previous<number<=1048576:raise ValueError('Duplicate or unordered row')
    previous=number;cells={};coords={}
    for cell in row.findall('m:c',NS):
     match=re.fullmatch(r'([A-Z]{1,3})([1-9][0-9]{0,6})',cell.attrib.get('r',''))
     if not match or int(match[2])!=number:raise ValueError('Cell address differs from worksheet row')
     col=0
     for char in match[1]:col=col*26+ord(char)-64
     if col>16384 or col in cells:raise ValueError('Duplicate or invalid cell')
     maxcol=max(maxcol,col);kind=cell.attrib.get('t');v=cell.find('m:v',NS);inline=cell.find('m:is',NS)
     value=v.text if v is not None else ''.join(t.text or '' for t in inline.iter('{'+NS['m']+'}t')) if inline is not None else None
     if cell.find('m:f',NS) is not None:formulas+=1
     if value is not None:
      if kind=='s':
       if not value.isdigit() or int(value)>=len(strings):raise ValueError('Invalid shared string index')
       value=strings[int(value)]
      elif kind=='b':
       if value not in ('0','1'):raise ValueError('Invalid boolean cell')
       value=value=='1'
      elif kind=='e':value={'excel_error':value}
      elif kind not in ('inlineStr','str','d'):
       value=float(value) if any(c in value.lower() for c in ['.','e']) else int(value)
       if isinstance(value,float) and not math.isfinite(value):raise ValueError('Nonfinite cell')
     cells[col]=value;coords[col]=cell.attrib['r']
    rows.append({'source_row':number,'values_by_column':cells,'coordinates_by_column':coords})
   if not rows:continue
   header=rows[0];columns=sorted(header['values_by_column']);headers=[header['values_by_column'][c] for c in columns]
   if not all(isinstance(h,str) and h.strip() for h in headers) or len(set(headers))!=len(headers):raise ValueError('Nonempty distinct result headers required')
   if any(c not in columns and value is not None for r in rows[1:] for c,value in r['values_by_column'].items()):raise ValueError('Data outside declared header columns cannot be discarded')
   records=[{'source_row':r['source_row'],'cells':[r['values_by_column'].get(c) for c in columns],'coordinates':[r['coordinates_by_column'].get(c) for c in columns]} for r in rows[1:]]
   tables.append({'sheet':sheet.attrib['name'],'part':target,'header_row':header['source_row'],'headers':headers,'header_coordinates':[header['coordinates_by_column'][c] for c in columns],'rows':records,'formula_cells_using_cached_values':formulas})
 return {'schema':'mindtec-collection-result-cut/1','identity_namespace':'scan_internal_envio_id','provenance':{'filename':path.name,'original_sha256':hashlib.sha256(raw).hexdigest(),'source_bytes':len(raw),'date_system':'excel_1904' if date1904 else 'excel_1900','adapter_version':VERSION,'adapter_sha256':hashlib.sha256(IMPLEMENTATION_BYTES).hexdigest()},'tables':tables}

def table_rows(table):return [{'source_row':r['source_row'],'values':dict(zip(table['headers'],r['cells'])),'coordinates':dict(zip(table['headers'],r['coordinates']))} for r in table['rows']]
