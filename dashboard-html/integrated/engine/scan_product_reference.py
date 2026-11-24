"""Exact current Scan master/alias joins; no fuzzy brand or product matching."""
import collections,csv,unicodedata

def key(value):return unicodedata.normalize('NFC',str(value or '')).strip().casefold()

class Reference:
 def __init__(self,catalogue,aliases,census_aliases=None,retained_label_aliases=None):
  self.retained_label_aliases=retained_label_aliases or {}
  self.products=[];self.codes=collections.defaultdict(list);self.labels=collections.defaultdict(list);self.aliases=collections.defaultdict(list)
  with open(catalogue,encoding='utf-8-sig',newline='') as f:
   reader=csv.DictReader(f,delimiter=';')
   for row in reader:
    row=dict(row,source_line=reader.line_num);self.products.append(row);self.labels[key(row['Valor del catálogo'])].append(row)
    if row['Código en Kobo']:self.codes[key(row['Código en Kobo'])].append(row)
  for filename in [aliases]+([census_aliases] if census_aliases else []):
   with open(filename,encoding='utf-8-sig',newline='') as f:
    reader=csv.DictReader(f,delimiter=';')
    for row in reader:
     if row.get('Valor del catálogo'):self.aliases[key(row['Texto leído'])].append(dict(row,source_line=reader.line_num,source_file=str(filename)))
 def canonical(self,row,trail=()):
  label=row['Valor del catálogo']
  if label in trail:return None
  merged=row.get('Unido en')
  if merged:
   candidates=self.labels[key(merged)]
   return self.canonical(candidates[0],trail+(label,)) if len(candidates)==1 else None
  return row if row.get('Activo')=='Sí' else None
 def unique(self,rows):
  candidates={}
  for row in rows:
   product=self.canonical(row)
   if product:candidates[product['Valor del catálogo']]=product
  return next(iter(candidates.values())) if len(candidates)==1 else None
 def resolve(self,code=None,label=None,selected=None):
  if code:
   product=self.unique(self.codes.get(key(code),[]))
   if product:return {'state':'matched','basis':'exact_current_Scan_Kobo_code','product':product}
  for value,source in [(label,'export_master_label'),(selected,'census_selected_label')]:
   if not value:continue
   product=self.unique(self.labels.get(key(value),[]))
   if product:return {'state':'matched','basis':'exact_current_Scan_'+source,'product':product}
   rows=self.aliases.get(key(value),[]);targets=[]
   for alias in rows:targets+=self.labels.get(key(alias['Valor del catálogo']),[])
   product=self.unique(targets)
   if product:return {'state':'matched','basis':'exact_published_Scan_alias_'+source,'product':product,'alias_sources':[{'file':a['source_file'],'line':a['source_line']} for a in rows]}
  if selected in self.retained_label_aliases:
   retained=self.retained_label_aliases[selected];product=self.unique(self.labels.get(key(retained),[]))
   if product:return {'state':'matched','basis':'retained_reviewed_label_alias_then_exact_current_Scan_master','product':product,'retained_alias':{'from':selected,'to':retained,'configuration_field':'price_label_aliases'}}
  return {'state':'unresolved_exact_reference','basis':'No unique current code, master label or published alias'}
