import io
import unittest
import zipfile
from xml.sax.saxutils import escape

from kobo_label_evidence import extract, M


def workbook(child_version='v1', parent_index='1', value='1', duplicate_metadata=False, formula=False):
    question='¿Qué SKUs / presentaciones de ${marca_lbl_bsa_energy} están disponibles en este punto de venta?'
    def sheet(rows):
        content=''
        for n, values in enumerate(rows, 1):
            cells=''.join('<c r="%s%s" t="inlineStr"><is><t>%s</t></is></c>' %
                          (chr(65+i), n, escape(v)) for i,v in enumerate(values))
            content+='<row r="%s">%s</row>' % (n,cells)
        return '<worksheet xmlns="'+M+'"><sheetData>'+content+'</sheetData></worksheet>'
    parent=sheet([['_id','__version__','_index','Duplicate','Duplicate'],['123','v1','1','','']])
    headers=['marca_act_bsa_energy','marca_lbl_bsa_energy','_submission__id',
             '_submission___version__','_parent_index',question,question+'/Red Bull 250 ml']
    row=['red_bull','Red Bull','123',child_version,parent_index,'Red Bull 250 ml',value]
    if duplicate_metadata:headers.append('_submission__id');row.append('123')
    child=sheet([headers,row])
    if formula:child=child.replace('<c r="G2" t="inlineStr">','<c r="G2" t="inlineStr"><f>1</f>')
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as z:
        z.writestr('xl/workbook.xml','<workbook xmlns="'+M+'" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Censo" r:id="r1"/><sheet name="rep_bsa_energy" r:id="r2"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships><Relationship Id="r1" Target="worksheets/p.xml"/><Relationship Id="r2" Target="worksheets/c.xml"/></Relationships>')
        z.writestr('xl/worksheets/p.xml',parent);z.writestr('xl/worksheets/c.xml',child)
    return stream.getvalue()


class KoboLabelEvidenceTests(unittest.TestCase):
    def test_exact_parent_version_and_coordinate_preserved(self):
        r=extract(workbook())
        self.assertEqual(r['summary']['selected_label_occurrences'],1)
        row=r['tables'][1]['records'][0]
        self.assertEqual(row['parent_binding_state'],'exact_id_index_version')
        self.assertEqual(row['selected_labels'][0]['coordinate'],'G2')
        self.assertEqual(row['selected_labels'][0]['header_coordinate'],'G1')
        self.assertEqual(row['selected_labels'][0]['label'],'Red Bull 250 ml')

    def test_version_mismatch_unresolved(self):
        self.assertEqual(extract(workbook(child_version='v2'))['summary']['unresolved_parent_bindings'],1)

    def test_parent_index_mismatch_unresolved(self):
        self.assertEqual(extract(workbook(parent_index='2'))['summary']['unresolved_parent_bindings'],1)

    def test_invalid_boolean_is_not_selected(self):
        r=extract(workbook(value='maybe'))
        self.assertEqual(r['summary']['selected_label_occurrences'],0)
        self.assertEqual(r['summary']['invalid_option_values'],1)

    def test_zero_is_not_presence(self):
        self.assertEqual(extract(workbook(value='0'))['summary']['selected_label_occurrences'],0)

    def test_duplicate_required_header_rejected(self):
        with self.assertRaises(ValueError):extract(workbook(duplicate_metadata=True))

    def test_formula_cache_rejected(self):
        with self.assertRaises(ValueError):extract(workbook(formula=True))


if __name__=='__main__':unittest.main()
