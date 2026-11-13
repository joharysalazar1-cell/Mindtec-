"""Read Scan's flat XLSX tables with the Python standard library (read only)."""
import re,zipfile,xml.etree.ElementTree as E
def read_scan_xlsx(path):
    ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(path) as z:
        strings=[]
        if 'xl/sharedStrings.xml' in z.namelist(): strings=[''.join(e.itertext()) for e in E.fromstring(z.read('xl/sharedStrings.xml')).findall('m:si',ns)]
        rels={r.attrib['Id']:r.attrib['Target'].lstrip('/') for r in E.fromstring(z.read('xl/_rels/workbook.xml.rels'))}
        result={}
        for sheet in E.fromstring(z.read('xl/workbook.xml')).find('m:sheets',ns):
            target=rels[sheet.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']]
            if not target.startswith('xl/'):target='xl/'+target
            rows=[]
            for row in E.fromstring(z.read(target)).findall('.//m:sheetData/m:row',ns):
                data={}
                for c in row:
                    v=c.find('m:v',ns);inline=c.find('m:is',ns)
                    v=v.text if v is not None else ''.join(inline.itertext()) if inline is not None else ''
                    data[re.sub('[0-9]','',c.attrib['r'])]=strings[int(v)] if c.attrib.get('t')=='s' and v else v
                rows.append(data)
            result[sheet.attrib['name']]=rows
        return result
