"""Shared Streamlit visuals for the MindTEC executive audit dashboard.

Presentation reads only from the active session. Never claims official KPIs
until the existing deterministic auditor has saved a reproducible result.
"""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import streamlit as st


_CSS_PATH = Path(__file__).with_name("dashboard.css")


def apply_visual_theme() -> None:
    """Install styles once per Streamlit rerun. No custom JS or remote assets."""
    st.markdown(
        "<style>" + _CSS_PATH.read_text(encoding="utf-8") + "</style>",
        unsafe_allow_html=True,
    )


def sidebar_brand() -> None:
    st.sidebar.markdown(
        '<div class="mt-brand"><div class="mt-logo">Mind<em>TEC</em></div>'
        '<div class="mt-brand-caption">INTELLIGENCE &amp; DATA AUDIT</div></div>',
        unsafe_allow_html=True,
    )
    st.sidebar.caption("Auditoría comercial · fuentes identificadas · evidencia reproducible")


def topbar() -> None:
    st.markdown(
        '<div class="mt-topbar"><strong>Dashboard de auditoría comercial</strong>'
        '<small>Vista de trabajo · Los resultados oficiales requieren validación</small></div>',
        unsafe_allow_html=True,
    )


def _session_counts() -> dict[str, int]:
    records = st.session_state.get("archivos_cargados", {})
    results = st.session_state.get("audit_results", {})
    findings = st.session_state.get("audit_findings", {})
    statuses = st.session_state.get("api_status", {})
    real = sum(
        r.get("origen") != "demo"
        and not str(r.get("nombre", "")).startswith("DEMO_")
        for r in records.values()
    )
    demo = len(records) - real
    return {
        "reales": real,
        "demo": demo,
        "expedientes": len(results),
        "hallazgos": len(findings),
        "api_ok": sum(s.get("estado") == "Actualizada" for s in statuses.values()),
    }


def _hero(eyebrow: str, title: str, description: str, compact: bool = False) -> None:
    # Only static, application-authored text may enter this HTML fragment.
    cls = "mt-hero mt-hero-compact" if compact else "mt-hero"
    st.markdown(
        f'<section class="{cls}"><span class="mt-eyebrow">{eyebrow}</span>'
        f"<h1>{title}</h1><p>{description}</p></section>",
        unsafe_allow_html=True,
    )


def _card(title: str, tag: str, description: str, action: str, target: str, navigate) -> None:
    with st.container(border=True):
        st.markdown(
            '<div class="mt-feature">'
            f'<span class="mt-feature-number">{tag}</span>'
            f"<h3>{title}</h3><p>{description}</p></div>",
            unsafe_allow_html=True,
        )
        st.button(action, on_click=navigate, args=(target,), use_container_width=True)


def render_home(navigate) -> None:
    _hero(
        "INTELIGENCIA COMERCIAL · CENTRO DE CONTROL",
        "Auditoría, indicadores y decisiones.",
        "Un espacio para incorporar fuentes, verificar integridad, reconstruir "
        "indicadores y explicar las diferencias. Sin confundir datos observados "
        "con resultados certificados.",
    )
    counts = _session_counts()
    cols = st.columns(4)
    for col, (label, value) in zip(
        cols,
        [
            ("Fuentes reales en sesión", counts["reales"]),
            ("Fuentes de demostración", counts["demo"]),
            ("Expedientes guardados", counts["expedientes"]),
            ("Hallazgos documentados", counts["hallazgos"]),
        ],
    ):
        with col:
            st.metric(label, value)
    st.markdown(
        '<div class="mt-section-label">01 / CICLO DE AUDITORÍA</div>',
        unsafe_allow_html=True,
    )
    a, b, c = st.columns(3)
    with a:
        _card(
            "Fuentes y periodos",
            "01 · EXTRACCIÓN",
            "Incorpora archivos de campo o consulta APIs autorizadas. "
            "Conserva el origen, el periodo y la huella de cada fuente.",
            "Revisar fuentes",
            "Fuentes automáticas",
            navigate,
        )
    with b:
        _card(
            "Control de integridad",
            "02 · VALIDACIÓN",
            "Detecta faltantes, duplicados y claves inconsistentes sin "
            "modificar los registros originales.",
            "Auditar base",
            "Auditoría de la base",
            navigate,
        )
    with c:
        _card(
            "Resultados contrastables",
            "03 · EXPLICACIÓN",
            "Confronta resultados comparables y registra evidencia, "
            "limitaciones y decisiones del analista.",
            "Abrir vista ejecutiva",
            "Dashboard ejecutivo",
            navigate,
        )

    st.markdown(
        '<div class="mt-section-label">02 / ESTADO DE LAS FUENTES</div>',
        unsafe_allow_html=True,
    )
    left, right = st.columns([1.7, 1])
    with left:
        if counts["reales"] == 0:
            st.markdown(
                '<div class="mt-empty"><strong>Modo demostración.</strong> '
                "Todavía no se han incorporado fuentes reales en esta sesión. "
                "Los ejemplos sintéticos no son indicadores comerciales de MindTEC.</div>",
                unsafe_allow_html=True,
            )
        else:
            st.success(
                f'{counts["reales"]} fuente(s) real(es) disponibles para análisis. '
                "Valida su periodo y definición antes de comparar indicadores."
            )
    with right:
        with st.container(border=True):
            st.metric("Conexiones API actualizadas", counts["api_ok"])
            st.caption("La extracción activa requiere servidor, permisos y contrato de datos.")

    st.markdown(
        '<p class="mt-footnote">Evidencia antes que apariencia: un indicador '
        "sin fórmula validada, denominador, universo y fuente no se certifica. "
        "Los resultados permanecen en la sesión hasta exportarlos.</p>",
        unsafe_allow_html=True,
    )


def _verified_indicators():
    """Return only numeric KPI results explicitly saved by the auditor."""
    items = []
    for title, record in st.session_state.get("audit_results", {}).items():
        if not title.startswith("Indicador ·"):
            continue
        table = record.get("tabla")
        if not isinstance(table, pd.DataFrame):
            continue
        if "valor_pct" not in table.columns or "indicador" not in table.columns:
            continue
        for _, row in table.iterrows():
            try:
                value = float(row["valor_pct"])
            except (ValueError, TypeError):
                continue
            if math.isfinite(value):
                items.append((str(row["indicador"]), value, title))
    return items


def render_executive(navigate) -> None:
    _hero(
        "VISTA EJECUTIVA · ALCANCE DE LA SESIÓN",
        "Resultados, evidencia y hallazgos.",
        "La vista muestra únicamente indicadores calculados y expedientes "
        "guardados en esta sesión; no recupera ni inventa automáticamente "
        "los 12 KPI oficiales del dashboard HTML histórico.",
        compact=True,
    )
    counts = _session_counts()
    kpis = _verified_indicators()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Fuentes reales", counts["reales"])
    col2.metric("Expedientes", counts["expedientes"])
    col3.metric("KPI calculados", len(kpis))
    col4.metric("Hallazgos guardados", counts["hallazgos"])

    st.markdown(
        '<div class="mt-section-label">01 / INDICADORES CALCULADOS</div>',
        unsafe_allow_html=True,
    )
    if kpis:
        for start in range(0, len(kpis), 4):
            cols = st.columns(4)
            for col, (label, value, _) in zip(cols, kpis[start:start+4]):
                with col:
                    st.metric(label, f"{value:,.2f} %")
        st.caption(
            "Indicadores calculados mediante el módulo de denominador explícito. "
            "Un cálculo guardado no implica certificación oficial."
        )
    else:
        st.info(
            "Todavía no hay KPI calculados y guardados. Ve a Indicadores "
            "verificables, documenta fórmula y universo, y guarda un resultado."
        )
        st.button(
            "Calcular un KPI",
            on_click=navigate,
            args=("Indicadores verificables",),
            type="primary",
        )

    st.markdown(
        '<div class="mt-section-label">02 / MATRIZ DE EVIDENCIAS</div>',
        unsafe_allow_html=True,
    )
    results = st.session_state.get("audit_results", {})
    findings = st.session_state.get("audit_findings", {})
    if not results:
        st.warning(
            "Sin expedientes en esta sesión. Ejecuta una auditoría o un "
            "contraste para mostrar sus resultados aquí."
        )
        st.button("Auditar datos", on_click=navigate, args=("Auditoría de la base",))
        return

    matrix = []
    for title, record in results.items():
        finding = findings.get(title, {})
        matrix.append(
            {
                "Resultado": title,
                "Filas de evidencia": len(record.get("tabla", [])),
                "Fecha UTC": record.get("fecha", "No registrada"),
                "Resolución": finding.get("resolucion", "Pendiente de revisión"),
                "¿Hay recomendación?": "Sí" if finding.get("recomendacion") else "No",
            }
        )
    st.dataframe(
        pd.DataFrame(matrix), hide_index=True, use_container_width=True
    )

    st.markdown(
        '<div class="mt-section-label">03 / TRAZABILIDAD DEL RESULTADO</div>',
        unsafe_allow_html=True,
    )
    selected = st.selectbox("Expediente para inspeccionar", list(results))
    item = results[selected]
    table = item.get("tabla")
    if isinstance(table, pd.DataFrame):
        st.dataframe(table, hide_index=True, use_container_width=True)
    with st.expander("Fuente, reglas y alcance"):
        st.json(item.get("metadata", {}))
    with st.expander("Hallazgo registrado"):
        finding = findings.get(selected)
        if finding:
            st.json(finding)
        else:
            st.caption("Pendiente de interpretación y aprobación por el analista.")
    st.button(
        "Abrir gestión de hallazgos",
        on_click=navigate,
        args=("Resultados y hallazgos",),
        type="primary",
    )
    st.caption(
        "No se mezclan valores del dashboard histórico con la sesión activa. "
        "Para una conciliación oficial, carga los dos cortes y confirma "
        "la equivalencia de periodo, unidad, fórmula y universo."
    )


def render_html_snapshot() -> None:
    """Read only trusted, locally generated HTML snapshots; never upload to GitHub."""
    _hero(
        "DASHBOARD ORIGINAL · VISUALIZACIÓN LOCAL",
        "Dashboard HTML y trazabilidad.",
        "Esta vista abre un informe HTML generado en este equipo. "
        "Es una fotografía del corte: no descarga datos nuevos, no alimenta "
        "automáticamente los módulos Streamlit y no certifica las cifras.",
        compact=True,
    )
    repo_root = Path(__file__).resolve().parents[4]
    candidates = {
        "Dashboard de auditoría y trazabilidad":
            repo_root / "dashboard-html" / "dist"
            / "MindTEC_Dashboard_con_auditoria_y_trazabilidad.html",
        "Informe completo local":
            repo_root / "INFORME_MINDTEC_COMPLETO.html",
    }
    available = {name: path for name, path in candidates.items() if path.is_file()}
    if not available:
        st.info(
            "No se encontró un HTML ejecutivo local. El archivo construido "
            "se busca en dashboard-html/dist/MindTEC_Dashboard_con_auditoria_y_trazabilidad.html. "
            "También se reconoce INFORME_MINDTEC_COMPLETO.html en la raíz del repositorio."
        )
        st.caption(
            "El dashboard HTML privado debe generarse localmente con "
            "dashboard-html/build.py y sus fuentes autorizadas. Nunca lo publiques "
            "en el repositorio ni en GitHub Pages."
        )
        return

    selected = st.selectbox("Corte local para visualizar", list(available))
    path = available[selected]
    st.caption(
        f"Archivo local: {path.name} · {path.stat().st_size / 1024 / 1024:.1f} MB. "
        "Su fecha y cobertura deben confirmarse con el manifiesto del corte."
    )
    st.warning(
        "Este reporte puede contener respuestas, facturas, IDs de visita y "
        "otros datos privados incrustados. Úsalo únicamente en un servidor "
        "local, sin acceso de red externo, y abre solo HTML que hayas "
        "generado o revisado tú."
    )
    enabled = st.checkbox(
        "Confirmo que este HTML es de confianza y la sesión está restringida al equipo local."
    )
    if not enabled:
        st.info("Confirma lo anterior para habilitar la vista HTML completa.")
        return
    size = path.stat().st_size
    if size > 60 * 1024 * 1024:
        st.error(
            "El HTML supera 60 MB. Para evitar fallos del navegador, "
            "abre la copia local fuera de Streamlit o genera un corte menor."
        )
        return
    try:
        html = path.read_text(encoding="utf-8-sig")
    except (UnicodeDecodeError, OSError):
        st.error("No fue posible abrir el HTML local. Comprueba la codificación y los permisos.")
        return
    st.components.v1.html(html, height=1050, scrolling=True)
    st.caption(
        "Los filtros de este HTML funcionan dentro de la vista, pero no "
        "actualizan las fuentes de la sesión Streamlit. Para comparar KPI "
        "oficiales utiliza el módulo Contraste de fuentes."
    )
