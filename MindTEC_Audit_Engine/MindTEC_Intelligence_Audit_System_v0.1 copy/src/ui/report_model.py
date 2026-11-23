"""Evidence-led executive audit report model; no inferred reliability percentage."""
from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from html import escape
import math

import pandas as pd


MATCHED = frozenset(("Coincidencia exacta", "Dentro de tolerancia"))
PAIRED_OTHER = frozenset(("Diferencia no explicada", "Medida faltante"))
MISSING = frozenset(("Solo en base", "Solo en referencia"))
AREAS = (
    "Distribución y cobertura",
    "Disponibilidad y quiebres",
    "Inventario y stock",
    "Precios",
    "Competencia y participación",
    "Cadencia temporal",
    "Portafolio y surtido",
    "Rendimiento comercial",
    "Calidad y confiabilidad",
    "Metodología",
    "Predicción y modelos",
    "Predicción operativa tienda-producto",
)


def _number(value):
    try:
        converted = float(value)
        return converted if math.isfinite(converted) else None
    except (ValueError, TypeError):
        return None


def build_report(source_records, source_metadata, results, findings, api_status=None, generated_at=None):
    """Summarize observed session artifacts, not sample representativeness or assurance."""
    api_status = api_status or {}
    generated_at = generated_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    sources = []
    for sid, r in source_records.items():
        meta = source_metadata.get(sid, {})
        demo = r.get("origen") == "demo" or str(r.get("nombre", "")).startswith("DEMO_")
        sources.append({
            "nombre": str(r.get("nombre", "Fuente sin nombre")),
            "sha256": str(sid),
            "origen": str(r.get("origen") or "Archivo de sesión"),
            "periodo": str(meta.get("periodo") or "Sin documentar"),
            "version": str(meta.get("version") or "Sin documentar"),
            "rol": str(meta.get("rol") or meta.get("tipo_base") or "Sin clasificar"),
            "demo": demo,
        })
    real_count = sum(not s["demo"] for s in sources)
    audit_controls, contrasts, kpis, other = [], [], [], []
    for title, entry in results.items():
        if not isinstance(entry, dict):
            continue
        table = entry.get("tabla")
        if not isinstance(table, pd.DataFrame):
            other.append({"titulo": str(title), "motivo": "Tabla no disponible"})
            continue
        meta = entry.get("metadata") or {}
        if str(title).startswith("Diagnóstico ·") and {"control", "casos"}.issubset(table.columns):
            for _, row in table.iterrows():
                val = _number(row.get("casos"))
                audit_controls.append({
                    "expediente": str(title),
                    "control": str(row.get("control", "")),
                    "casos": int(val) if val is not None and val >= 0 else None,
                    "detalle": str(row.get("detalle") or ""),
                })
        elif str(title).startswith("Contraste ·") and "estado" in table.columns:
            statuses = Counter(table["estado"].fillna("Sin estado").astype(str))
            numerically_compared = sum(statuses.get(s, 0) for s in MATCHED | PAIRED_OTHER)
            accepted = sum(statuses.get(s, 0) for s in MATCHED)
            contrasts.append({
                "titulo": str(title),
                "filas": len(table),
                "pares_numericos": numerically_compared,
                "dentro_tolerancia": accepted,
                "diferencia_no_explicada": statuses.get("Diferencia no explicada", 0),
                "medida_faltante": statuses.get("Medida faltante", 0),
                "solo_una_fuente": sum(statuses.get(s, 0) for s in MISSING),
                "estados": dict(statuses),
                "definicion": str(meta.get("definicion") or "No documentada"),
                "fecha": str(entry.get("fecha") or "No registrada"),
            })
        elif str(title).startswith("Indicador ·") and {"indicador", "valor_pct"}.issubset(table.columns):
            for _, row in table.iterrows():
                value = _number(row.get("valor_pct"))
                if value is None:
                    continue
                kpis.append({
                    "nombre": str(row["indicador"]),
                    "valor_pct": value,
                    "numerador": _number(row.get("numerador")),
                    "denominador": _number(row.get("denominador")),
                    "definicion": str(meta.get("definicion") or "No documentada"),
                    "fuente": str(meta.get("sha256") or "Sin huella vinculada"),
                    "fecha": str(entry.get("fecha") or "No registrada"),
                    "estado": "Cálculo de sesión · sin certificación oficial",
                })
        else:
            other.append({"titulo": str(title), "filas": len(table)})
    findings_rows = []
    for title, row in findings.items():
        findings_rows.append({
            "expediente": str(title),
            "resolucion": str(row.get("resolucion") or "Pendiente"),
            "interpretacion": str(row.get("interpretacion") or ""),
            "limitaciones": str(row.get("limitaciones") or ""),
            "recomendacion": str(row.get("recomendacion") or ""),
        })
    warnings = [r for r in audit_controls if r["casos"] is not None and r["casos"] > 0]
    if real_count == 0:
        conclusion = "Solo hay fuentes de demostración: no es posible emitir una conclusión sobre datos empresariales."
    elif not results:
        conclusion = "Hay fuentes reales disponibles, pero no se registraron resultados de auditoría en esta sesión."
    else:
        conclusion = (
            "Existen resultados reproducibles de sesión, pero el alcance y las reglas "
            "oficiales aún deben acreditarse antes de emitir un dictamen integral."
        )
    return {
        "generado_utc": generated_at,
        "conclusion": conclusion,
        "estado": "Validación interna en curso · sin opinión de aseguramiento",
        "fuentes": sources,
        "fuentes_reales": real_count,
        "fuentes_demo": len(sources) - real_count,
        "expedientes": len(results),
        "controles": audit_controls,
        "controles_con_casos": len(warnings),
        "contrastes": contrasts,
        "kpis": kpis,
        "hallazgos": findings_rows,
        "otros": other,
        "api_actualizadas": sum(v.get("estado") == "Actualizada" for v in api_status.values()),
    }


def _fmt(v, digits=2):
    if v is None:
        return "No informado"
    return f"{v:,.{digits}f}"


def _td(text):
    return "<td>" + escape(str(text)) + "</td>"


def _table(headers, rows):
    if not rows:
        return '<p class="muted">Sin evidencia disponible en esta sesión.</p>'
    header = "".join("<th>" + escape(str(x)) + "</th>" for x in headers)
    body = "".join("<tr>" + "".join(_td(v) for v in row) + "</tr>" for row in rows)
    return "<table><thead><tr>" + header + "</tr></thead><tbody>" + body + "</tbody></table>"


def export_html(report):
    """Printable standalone HTML: summary only, escaped inputs, no raw source rows."""
    css = """
    :root{--ink:#20324e;--navy:#20324e;--blue:#4267ca;--orange:#e97d4e;--line:#e1e7ef;--muted:#65758a}
    *{box-sizing:border-box}body{margin:0;font:14px/1.6 Segoe UI,Arial,sans-serif;color:var(--ink);background:#f2f5fa}
    main{max-width:1120px;margin:30px auto;background:white;padding:42px 54px;box-shadow:0 5px 25px #20324e10}
    header{border-bottom:4px solid var(--orange);padding-bottom:25px;margin-bottom:30px}
    .eyebrow{font-size:10px;color:var(--orange);font-weight:bold;letter-spacing:2px}
    h1{font-size:34px;line-height:1.2;letter-spacing:-1px;margin:7px 0}h2{font-size:19px;margin:32px 0 12px;padding-bottom:8px;border-bottom:1px solid var(--line)}
    h3{font-size:14px;margin:20px 0 6px}.muted{color:var(--muted);font-size:12px}
    .summary{background:#edf3fb;border-left:4px solid var(--blue);padding:16px 20px;border-radius:3px;margin:17px 0}
    .status{display:inline-block;padding:5px 9px;background:#fff3e9;color:#845329;font-size:11px;border-radius:6px;font-weight:700}
    .metrics{display:flex;gap:12px;flex-wrap:wrap;margin-top:18px}.metric{border:1px solid var(--line);padding:15px;flex:1;min-width:130px}
    .metric strong{display:block;font-size:27px}.metric small{color:var(--muted)}
    table{width:100%;border-collapse:collapse;font-size:11px;margin:12px 0 17px}th,td{text-align:left;vertical-align:top;border-bottom:1px solid var(--line);padding:9px 10px;overflow-wrap:anywhere}
    th{background:#eef2f8;font-weight:700}.note{background:#fff8f1;padding:13px 17px;border-left:3px solid var(--orange);font-size:12px}
    footer{border-top:1px solid var(--line);padding-top:18px;color:var(--muted);font-size:11px;margin-top:38px}
    @page{size:A4;margin:15mm}@media print{body{background:white}main{margin:0;padding:0;box-shadow:none;max-width:none}h2,h3{break-after:avoid}table{break-inside:auto}tr{break-inside:avoid}}
    """
    metrics = [
        ("Fuentes reales", report["fuentes_reales"]),
        ("Expedientes", report["expedientes"]),
        ("KPI calculados", len(report["kpis"])),
        ("Contrastes", len(report["contrastes"])),
        ("Hallazgos guardados", len(report["hallazgos"])),
    ]
    metric_html = "".join(
        '<div class="metric"><strong>' + escape(str(v)) + '</strong><small>'
        + escape(k) + "</small></div>" for k, v in metrics
    )
    source_rows = [
        (r["nombre"], r["periodo"], r["rol"], "Demo" if r["demo"] else "No demo", r["sha256"][:12])
        for r in report["fuentes"]
    ]
    kpi_rows = [
        (r["nombre"], f'{_fmt(r["valor_pct"])}%', _fmt(r["numerador"], 0),
         _fmt(r["denominador"], 0), r["definicion"], r["estado"])
        for r in report["kpis"]
    ]
    contrast_rows = [
        (r["titulo"], r["filas"], r["pares_numericos"], r["dentro_tolerancia"],
         r["diferencia_no_explicada"], r["medida_faltante"], r["solo_una_fuente"])
        for r in report["contrastes"]
    ]
    controls_rows = [
        (r["expediente"], r["control"], r["casos"], r["detalle"])
        for r in report["controles"] if r["casos"] is not None and r["casos"] > 0
    ]
    findings_rows = [
        (r["expediente"], r["resolucion"], r["interpretacion"],
         r["limitaciones"], r["recomendacion"])
        for r in report["hallazgos"]
    ]
    actions = (
        ("01", "Formalizar fórmula, universo, exclusiones, pesos y vigencia de cada KPI", "Investigación y Sistemas", "Diccionario versionado y aprobado"),
        ("02", "Conciliar visita, tienda, SKU y factura con el corte oficial", "Datos y Operaciones", "Matriz de discrepancias con evidencia"),
        ("03", "Reproducir los cálculos con un procedimiento independiente", "Auditoría de datos", "Cuaderno de pruebas, hashes y resultados"),
        ("04", "Explicar diferencias materiales, pendientes y no aplicables", "Analista y responsable del dato", "Registro de resolución firmado"),
        ("05", "Separar reporte ejecutivo de expedientes con datos sensibles", "Sistemas y Seguridad", "Control de accesos y política de conservación"),
    )
    return (
        '<!doctype html><html lang="es"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<title>MindTEC · Informe ejecutivo de auditoría</title><style>'
        + css + '</style></head><body><main><header><div class="eyebrow">MINDTEC · INTELLIGENCE &amp; DATA AUDIT</div>'
        '<h1>Informe ejecutivo de calidad, trazabilidad y conciliación</h1>'
        '<p class="muted">Uso interno · Resumen de la sesión · Fecha UTC: '
        + escape(report["generado_utc"])
        + '</p><span class="status">' + escape(report["estado"]) + '</span></header>'
        '<h2>1. Conclusión para dirección</h2><div class="summary">'
        + escape(report["conclusion"]) + '</div>'
        '<p>Este documento resume evidencia disponible, no una opinión de auditoría externa. '
        'No existe un porcentaje global de confiabilidad calculado o certificado.</p>'
        '<div class="metrics">' + metric_html + '</div>'
        '<h2>2. Alcance y procedencia de las fuentes</h2>'
        + _table(("Archivo", "Periodo declarado", "Rol", "Tipo", "SHA-256 (prefijo)"), source_rows)
        + '<p class="muted">Los identificadores son prefijos para navegación: usar la huella completa del expediente técnico para verificación.</p>'
        '<h2>3. Indicadores calculados con denominador explícito</h2>'
        + _table(("Indicador", "Valor", "Numerador", "Denominador", "Definición", "Condición"), kpi_rows)
        + '<h2>4. Conciliación con otras fuentes</h2>'
        + _table(("Contraste", "Filas", "Pares numéricos", "Coincidencia/tolerancia", "Diferencia no explicada", "Medida faltante", "Una sola fuente"), contrast_rows)
        + '<p class="muted">Los conteos no son un porcentaje de confiabilidad global. Las tolerancias solo aplican al alcance definido en cada contraste.</p>'
        '<h2>5. Excepciones de integridad detectadas</h2>'
        + _table(("Expediente", "Control", "Casos reportados", "Detalle"), controls_rows)
        + '<p class="muted">Un registro puede activar múltiples controles; los casos no se suman como si fueran observaciones únicas.</p>'
        '<h2>6. Hallazgos y resolución del analista</h2>'
        + _table(("Expediente", "Resolución", "Interpretación", "Limitaciones", "Recomendación"), findings_rows)
        + '<h2>7. Plan de cierre propuesto</h2>'
        + _table(("Fase", "Acción", "Responsable sugerido", "Criterio de cierre"), actions)
        + '<h2>8. Marco integral de revisión (12 dimensiones)</h2>'
        + _table(("Dimensión", "Cobertura"), [(x, "Requiere comprobación documental por separado") for x in AREAS])
        + '<div class="note"><b>Limitaciones:</b> el informe no demuestra representatividad muestral, '
        'exactitud de las fórmulas comerciales oficiales ni vigencia histórica de configuraciones. '
        'Un cálculo reproducible no equivale a un indicador comercial certificado. '
        'Sin datos empresariales reales, el contenido será únicamente demostrativo.</div>'
        '<footer>MindTEC · Informe interno generado desde los expedientes de la sesión. '
        'Prohibida su distribución sin autorización. Elaboración independiente; '
        'no asociado, emitido ni certificado por PwC ni por otra firma de auditoría.</footer>'
        '</main></body></html>'
    )
