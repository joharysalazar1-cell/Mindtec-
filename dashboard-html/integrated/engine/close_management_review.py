"""Evidence-bound review of executive priorities; never writes source answers."""
import collections
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = ROOT / 'private/platform-recovered-2026-11-23'
SITE = ROOT.parent.parent / 'mindtec-web/app-site'
OUT = SITE / 'source/management-review-2026-11-24'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def build():
    paths = [BASE/'invoice-cut-retained.json', BASE/'soc24u/integrated-result.json',
             BASE/'skus_resueltos_2026-11-24.csv', SITE/'source/executive-cut-2026-11-19/anomalies.json',
             SITE/'source/comparison-cut-2026-11-24/result.json']
    hashes = {str(path.relative_to(ROOT.parent.parent)): digest(path) for path in paths}
    cut, p, anomalies, comparison = read(paths[0]), read(paths[1]), read(paths[3]), read(paths[4])
    rows = {r['source_row']: dict(zip(cut['headers'], r['cells'])) for r in cut['rows']}
    aliases = list(csv.DictReader(paths[2].open(encoding='utf-8-sig', newline=''), delimiter=';'))
    columns = {name: index for index, name in enumerate(cut['headers'])}
    def coordinate(field, row):
        n = columns[field]+1
        col = ''
        while n:
            n, rem = divmod(n-1, 26)
            col = chr(65+rem)+col
        return col+str(row)
    def evidence(index):
        out = []
        for ref in p['evidence_sets'][index]:
            answer = p['answer_evidence'].get(ref)
            for cid in answer['cell_ids'] if answer else [ref]:
                cell = p['cells'].get(cid)
                if cell:
                    out.append(dict(cell_id=cid, **cell, route=answer.get('route') if answer else None))
        return list({x['cell_id']: x for x in out}.values())
    documents = collections.defaultdict(list)
    for rownum, row in rows.items():
        documents[row['ID factura']].append((rownum, row))
    reviewed = []
    for anomaly in anomalies['rows']:
        n = anomaly['fila_excel']; row = rows[n]
        missing = [field for field in ['ID SKU', 'Fecha de emisión', 'Precio unitario'] if row[field] is None]
        status = 'evidence_required'
        actions = []
        checks = []
        if row['Precio unitario'] == 0:
            if 'BONIFICACION' in (row['Texto leído'] or '').upper() and row['Total neto'] == 0:
                status = 'documented_bonus'
                actions.append('Cero comercial explicado por bonificación explícita en el texto original. Se conserva; no entra como precio positivo de referencia.')
            else:
                actions.append('Precio y neto cero conservados. Sin mención explícita de bonificación: requiere comprobante; no se transforma en venta pagada ni precio de referencia.')
        if 'Fecha de emisión' in missing:
            candidates = sorted({v['Fecha de emisión'] for _, v in documents[row['ID factura']] if v['Fecha de emisión'] is not None})
            checks.append(dict(check='same_document_date', candidate_dates=candidates,
                               rows=[n for n, _ in documents[row['ID factura']]]))
            actions.append('Se buscaron fechas en todas las líneas del mismo ID de documento; no hay fecha de emisión recuperable.' if not candidates else 'Existe fecha en otra línea; no se sobreescribe sin validar la identidad documental.')
        if 'ID SKU' in missing:
            exact = [v for v in aliases if v['Texto leído'].strip().casefold() == (row['Texto leído'] or '').strip().casefold()]
            checks.append(dict(check='current_Scan_exact_invoice_alias', matches=[{
                'text':v['Texto leído'], 'label':v['Valor del catálogo'], 'code':v['Código en Kobo'], 'state':v['Estado']} for v in exact]))
            if exact and all(v['Estado']=='Sin valor' and not v['Código en Kobo'] for v in exact):
                actions.append('Scan clasifica exactamente este texto como «Sin valor». Se conserva sin SKU; no se fabrica un producto ni se incorpora al análisis de marcas.')
            else:
                actions.append('No existe alias exacto aprobado en Scan para identificar un SKU único. Se mantiene fuera del análisis por producto hasta tener identidad comprobable.')
        if 'Precio unitario' in missing:
            actions.append('No se rellena con total/cantidad: precio de lista, unidades, descuentos y cargos no están certificados. La línea conserva su total documental cuando es utilizable por esa métrica.')
        need = []
        if 'ID SKU' in missing: need.append('producto, presentación y código aprobado en Scan')
        if 'Fecha de emisión' in missing: need.append('fecha visible del comprobante')
        if 'Precio unitario' in missing: need.append('precio unitario y unidad de facturación visibles')
        if row['Precio unitario']==0 and status!='documented_bonus':need.append('comprobante que explique el cero comercial')
        fields=['Texto leído','ID SKU','Fecha de emisión','Precio unitario','Cantidad','Total neto']
        reviewed.append(dict(source_row=n, month=row['Mes'],store=row['Sticker'],document=row['ID factura'],
                             line=row['Línea'],text=row['Texto leído'],status=status,missing=missing,
                             actions=actions,needed=need,checks=checks,evidence=[dict(field=f,coordinate=coordinate(f,n),value=row[f]) for f in fields]))
    availability=[]
    counts=collections.defaultdict(collections.Counter)
    for s in p['availability']['stores']:
        visit=p['visits'][s['v']];code=p['availability']['companies'][s['company']]
        if not s['questionnaire_covers_company']:
            state='not_asked'
        elif s['eligible'] is False:
            state='not_a_declared_buyer'
        elif s['state']=='complete' and s['no_declared_stockout'] in (0,1):
            state='declared_stockout' if s['no_declared_stockout']==0 else 'declared_no_stockout'
        else:state='unresolved_declaration'
        counts[visit['month']][state]+=1
        availability.append(dict(**visit,company=code,classification=state,original_state=s['state'],
                                 eligible=s['eligible'],no_declared_stockout=s['no_declared_stockout'],
                                 evidence=evidence(s['evidence_set'])))
    discrepancies=[]
    for inv in p['inventories']:
        if inv['state']!='pending':continue
        ev=evidence(inv['evidence_set']);cat=p['categories'][inv['category']]
        choice=[x for x in ev if (x.get('route') or '').endswith('/marcas_'+cat)]
        selected=set(str(choice[0]['value']).split()) if len(choice)==1 and choice[0]['value'] else set()
        repeats={x['code'] for x in inv['rows'] if x['code']}
        if inv['other_branches']:repeats.add('otras_marcas')
        discrepancies.append(dict(**p['visits'][inv['v']],category=cat,known_faces=inv['known_faces'],
                                  selected=sorted(selected),repeated=sorted(repeats),
                                  only_selected=sorted(selected-repeats),only_repeated=sorted(repeats-selected),
                                  rows=inv['rows'],signals=inv['signals'],evidence=ev,
                                  treatment='Conservar caras observadas y límites; no eliminar repeticiones ni completar selecciones por inferencia. La suma observada no demuestra que el inventario esté completo.'))
    parent_checks=[]
    for f in p['findings']:
        ev=f['finding']['evidence'];parent_checks.append(dict(kobo_id=ev['kobo_id'],month=ev['month'],
            rule=f['finding']['rule'],categories=ev['categories'],
            evidence=[dict(cell_id=cid,**p['cells'][cid]) for cid in ev['cell_ids']]))
    methods=[]
    for i,name in enumerate(comparison['names']):
        sample=next((r for r in comparison['rows'] if r['metric']==i and r['kind']=='month' and r['window']==90),None)
        methods.append(dict(metric=i,name=name,formula=comparison['formulas'][i],
                            sample_run=sample['audit_run'] if sample else None,
                            state='documented_operational_method_not_official_certification'))
    result=dict(schema='mindtec-management-review/1',date='2026-11-24',version='1.0.0',
                source_hashes=hashes,original_workbook=cut['provenance'],
                no_source_answers_changed=True,no_new_field_confirmation=True,
                summary=dict(invoice_reviewed=len(reviewed),documented_bonus=sum(x['status']=='documented_bonus' for x in reviewed),
                             invoice_requires_evidence=sum(x['status']=='evidence_required' for x in reviewed),
                             availability_by_month={k:dict(v) for k,v in counts.items()},
                             shelf_discrepancies=len(discrepancies),shelf_visits=len({x['kobo_id'] for x in discrepancies}),
                             parent_discrepancies=len(parent_checks),operational_methods=len(methods)),
                invoice_review=reviewed,availability_review=availability,shelf_review=discrepancies,
                parent_review=parent_checks,methods=methods)
    for path in paths:assert digest(path)==hashes[str(path.relative_to(ROOT.parent.parent))]
    OUT.mkdir(parents=True,exist_ok=True)
    target=OUT/'result.json';target.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    (OUT/'receipt.json').write_text(json.dumps(dict(version=result['version'],result_sha256=digest(target),source_hashes=hashes),ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result['summary'],ensure_ascii=False))

if __name__=='__main__':build()
