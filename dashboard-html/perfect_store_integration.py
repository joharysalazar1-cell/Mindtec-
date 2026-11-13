"""Attach a prepared private Perfect Store cut without changing historical KPI data."""
import json
def integrate_perfect_store(template, data, private_dir):
    folder=private_dir/'Perfect_Store_reconstruido_2026-11-13'
    report=folder/'MindTEC_Perfect_Store_reconstruido.html'
    summary=folder/'resumen_por_marca_mes.json'
    if not report.exists() or not summary.exists(): return template
    embedded=report.read_text(encoding='utf-8').replace('<meta charset="utf-8">','<meta charset="utf-8"><base href="./Perfect_Store_reconstruido_2026-11-13/">',1)
    data['perfectStore']={'summary':json.loads(summary.read_text(encoding='utf-8')),'html':embedded,'cut':'2026-11-13'}
    section='<section id="perfect-store"><span class="section-label">RECONSTRUCCIÓN DESDE ENCUESTAS SCAN · 13/11/2026</span><h2>Perfect Store con trazabilidad por tienda</h2><div class="card"><div id="perfect-store-summary"></div><button id="perfect-store-open">Abrir componentes y respuestas por tienda</button><p class="muted">Corte operativo independiente del archivo histórico. Conserva los pendientes y las diferencias de reglas de SKU núcleo y frío.</p></div><iframe id="perfect-store-frame" title="Perfect Store: cálculo y respuestas originales" style="display:none;width:100%;height:1000px;border:1px solid #d5dfec;border-radius:10px;background:white" loading="lazy"></iframe></section>'
    template=template.replace('<section id="trazabilidad">',section+'<section id="trazabilidad">',1)
    template=template.replace('<a href="#estadistica">Estadística y χ²</a>','<a href="#perfect-store">Perfect Store reconstruido</a><a href="#estadistica">Estadística y χ²</a>',1)
    return template
