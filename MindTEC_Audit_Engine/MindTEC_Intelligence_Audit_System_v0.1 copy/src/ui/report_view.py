"""Presentation-ready, evidence-based report for MindTEC direction."""
from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from src.ui.dashboard import _hero
from src.ui.report_model import AREAS, build_report, export_html


PLAN = [
    {
        "Prioridad": "P1",
        "Control / decisión": "Aprobar reglas de los KPI: universo, numerador, denominador, pesos, versiones y no aplicables",
        "Responsable sugerido": "Investigación + Sistemas",
        "Cierre verificable": "Diccionario técnico versionado y validado",
    },
    {
        "Prioridad": "P1",
        "Control / decisión": "Reconciliar encuestas, tiendas, facturas, catálogo y exportaciones del dashboard",
        "Responsable sugerido": "Datos + Operaciones",
        "Cierre verificable": "Conciliación por clave, periodo y fuente con excepciones explicadas",
    },
    {
        "Prioridad": "P2",
        "Control / decisión": "Reconstruir cada indicador de manera independiente y registrar tolerancias",
        "Responsable sugerido": "Auditoría de datos",
        "Cierre verificable": "Pruebas reproducibles y diferencias clasificadas",
    },
    {
        "Prioridad": "P2",
        "Control / decisión": "Resolver alertas documentadas y aprobar el dictamen de cada KPI",
        "Responsable sugerido": "Responsable de negocio",
        "Cierre verificable": "Expediente con evidencia, responsable y resolución",
    },
    {
        "Prioridad": "P3",
        "Control / decisión": "Automatizar extracciones autorizadas y revisión de cambios entre cortes",
        "Responsable sugerido": "Sistemas + Seguridad",
        "Cierre verificable": "Pipeline probado, roles, alertas y retención autorizada",
    },
]


def _section(text: str):
    st.markdown(f'<div class="mt-section-label">{text}</div>', unsafe_allow_html=True)


def _evidence_ratio(report):
    """Purely descriptive count; never labelled reliability or confidence."""
    pairs = sum(x["pares_numericos"] for x in report["contrastes"])
    ok = sum(x["dentro_tolerancia"] for x in report["contrastes"])
    return ok, pairs


def render_report(navigate) -> None:
    _hero(
        "INFORME PARA DIRECCIÓN · AUDITORÍA INTERNA DE DATOS",
        "Calidad, trazabilidad y confianza sustentada.",
        "Evaluación ejecutiva del alcance disponible: datos, controles, "
        "conciliación, hallazgos y decisiones. Un cálculo verificable no "
        "constituye por sí solo una certificación de los 12 KPI oficiales.",
        compact=True,
    )

    report = build_report(
        st.session_state.get("archivos_cargados", {}),
        st.session_state.get("source_metadata", {}),
        st.session_state.get("audit_results", {}),
        st.session_state.get("audit_findings", {}),
        st.session_state.get("api_status", {}),
    )

    st.caption(
        "USO INTERNO · Informe generado en UTC "
        + report["generado_utc"]
        + " · Validación interna, no opinión de auditoría externa"
    )
    _section("01 / CONCLUSIÓN PARA EL COMITÉ")
    st.warning(report["conclusion"])
    st.markdown(
        "**Estado del dictamen:** Validación interna en curso. "
        "No se presenta una tasa de confiabilidad global porque la cobertura, "
        "la calidad de las fuentes y la equivalencia con las reglas oficiales "
        "deben acreditarse por separado."
    )

    c = st.columns(5)
    for col, (label, value) in zip(c, [
        ("Fuentes reales", report["fuentes_reales"]),
        ("Expedientes", report["expedientes"]),
        ("KPI calculados", len(report["kpis"])),
        ("Contrastes", len(report["contrastes"])),
        ("Hallazgos guardados", len(report["hallazgos"])),
    ]):
        col.metric(label, value)
    st.caption(
        f'{report["fuentes_demo"]} fuente(s) de demostración separadas de las reales. '
        "Ninguno de estos conteos representa una certificación de exactitud."
    )

    summary_tab, kpi_tab, issue_tab, approach_tab = st.tabs([
        "Síntesis ejecutiva",
        "Indicadores y conciliación",
        "Excepciones y plan de acción",
        "Alcance, método y evidencias",
    ])
    with summary_tab:
        _section("02 / LECTURA EJECUTIVA")
        left, right = st.columns([1.4, 1])
        with left:
            st.subheader("Qué podemos afirmar")
            if report["fuentes_reales"] == 0:
                st.info("Sesión de demostración. No hay base suficiente para presentar cifras reales de MindTEC.")
            else:
                st.success(
                    f'Se identificaron {report["fuentes_reales"]} fuentes reales. '
                    "Sus periodos, roles y reglas deben validarse con los responsables."
                )
            if report["expedientes"]:
                st.write(
                    f'Se han guardado {report["expedientes"]} expedientes de auditoría, '
                    "reconciliación o indicadores en la sesión."
                )
            else:
                st.write("No se ha guardado ningún expediente en esta sesión.")
            ok, paired = _evidence_ratio(report)
            st.write(
                f'Comparaciones numéricas dentro de tolerancia: {ok} de {paired} '
                "pares en los contrastes ejecutados."
            )
            st.caption(
                "Los pares pertenecen a los cortes y definiciones seleccionados; "
                "la cifra no es una probabilidad de veracidad del dashboard."
            )
        with right:
            with st.container(border=True):
                st.markdown("**Posición de aseguramiento**")
                st.write("1. Evidencia identificable y auditable")
                st.write("2. Controles reproducibles")
                st.write("3. Reglas de negocio aprobadas")
                st.write("4. Diferencias resueltas y documentadas")
                st.write("5. Revisión responsable e independiente")
                st.caption("Son criterios propuestos para cierre; no acreditados automáticamente.")
        st.divider()
        st.subheader("Perspectiva integral: 12 dimensiones de análisis")
        st.caption(
            "Estas son las 12 aristas de investigación del proyecto, no 12 KPI "
            "ya reconstruidos. La cobertura no se infiere por semejanza de nombres."
        )
        table = pd.DataFrame({
            "Dimensión": list(AREAS),
            "Estado de validación": ["Por evaluar documentalmente"] * len(AREAS),
        })
        st.dataframe(table, hide_index=True, use_container_width=True, height=290)

    with kpi_tab:
        _section("03 / CIFRAS CON DEFINICIÓN Y DENOMINADOR")
        if report["kpis"]:
            kpi_rows = [{
                "Indicador": x["nombre"],
                "Resultado (%)": round(x["valor_pct"], 2),
                "Numerador": x["numerador"],
                "Denominador": x["denominador"],
                "Estado": x["estado"],
            } for x in report["kpis"]]
            st.dataframe(pd.DataFrame(kpi_rows), hide_index=True, use_container_width=True)
            st.caption(
                "Las fórmulas se consignan en cada expediente. "
                "Ningún indicador adquiere carácter oficial por estar calculado."
            )
        else:
            st.info(
                "No se han guardado KPI con numerador y denominador explícitos. "
                "El módulo Indicadores verificables permite producirlos."
            )
            st.button("Calcular un indicador", key="report_compute", on_click=navigate, args=("Indicadores verificables",))

        _section("04 / CONCILIACIÓN ENTRE FUENTES")
        if report["contrastes"]:
            cols = ["Contraste", "Filas", "Pares numéricos", "Dentro de tolerancia", "Diferencias",
                    "Medida faltante", "Solo una fuente"]
            data = [{
                cols[0]: x["titulo"],
                cols[1]: x["filas"],
                cols[2]: x["pares_numericos"],
                cols[3]: x["dentro_tolerancia"],
                cols[4]: x["diferencia_no_explicada"],
                cols[5]: x["medida_faltante"],
                cols[6]: x["solo_una_fuente"],
            } for x in report["contrastes"]]
            st.dataframe(pd.DataFrame(data), hide_index=True, use_container_width=True)
            if len(report["contrastes"]) == 1:
                vals = report["contrastes"][0]["estados"]
                chart = pd.DataFrame(
                    {"Estado": list(vals), "Observaciones": list(vals.values())}
                ).set_index("Estado")
                st.bar_chart(chart, horizontal=True, height=240)
            else:
                st.caption(
                    "Se muestran contrastes separados para no agregar periodos, "
                    "universos o indicadores potencialmente diferentes."
                )
            with st.expander("Definiciones y tolerancias documentadas"):
                for item in report["contrastes"]:
                    st.write(item["titulo"])
                    st.caption(item["definicion"])
        else:
            st.info("Sin resultados de reconciliación guardados en esta sesión.")
            st.button("Contrastar fuentes", key="report_contrast", on_click=navigate, args=("Contraste de fuentes",))
        st.caption(
            "Coincidencia matemática no es equivalencia de fuentes. Verifica "
            "periodo, población, fórmula, versión y exclusiones antes de interpretar diferencias."
        )

    with issue_tab:
        _section("05 / EXCEPCIONES TÉCNICAS Y RIESGOS")
        exceptions = [x for x in report["controles"] if x["casos"] is not None and x["casos"] > 0]
        if exceptions:
            st.dataframe(pd.DataFrame(exceptions), hide_index=True, use_container_width=True)
        else:
            st.info("Sin controles de integridad con casos positivos registrados en esta sesión.")
        st.caption(
            "Los casos de diferentes controles pueden corresponder al mismo registro. "
            "No deben sumarse para calcular una tasa global de error."
        )
        st.subheader("Registro de hallazgos")
        if report["hallazgos"]:
            st.dataframe(pd.DataFrame(report["hallazgos"]), hide_index=True, use_container_width=True)
        else:
            st.info(
                "Aún no se ha documentado una conclusión de analista. "
                "Las anomalías detectadas no equivalen automáticamente a errores confirmados."
            )
        st.subheader("Matriz de riesgos para revisión")
        st.dataframe(pd.DataFrame([
            {
                "Riesgo potencial": "Fórmulas y pesos históricos sin validar",
                "Consecuencia": "Diferencias metodológicas frente al panel",
                "Respuesta": "Obtener versiones de reglas por marca, canal y mes",
                "Prioridad": "A asignar",
            },
            {
                "Riesgo potencial": "Universos de encuestas y facturas no equivalentes",
                "Consecuencia": "Indicadores con denominador incorrecto",
                "Respuesta": "Conciliar claves, exclusiones y ventanas de tiempo",
                "Prioridad": "A asignar",
            },
            {
                "Riesgo potencial": "Extracciones y HTML de cortes diferentes",
                "Consecuencia": "Comparaciones temporalmente inválidas",
                "Respuesta": "Manifiesto del corte, SHA-256 y fecha de actualización",
                "Prioridad": "A asignar",
            },
            {
                "Riesgo potencial": "Exposición de registros en informes HTML",
                "Consecuencia": "Acceso indebido a evidencia empresarial",
                "Respuesta": "Separar informe ejecutivo y expediente técnico restringido",
                "Prioridad": "A asignar",
            },
        ]), hide_index=True, use_container_width=True)
        st.caption(
            "Riesgos metodológicos generales identificados durante el diseño. "
            "No son incidentes confirmados ni tienen una severidad medida."
        )
        _section("06 / PLAN DE CIERRE PROPUESTO")
        st.dataframe(pd.DataFrame(PLAN), hide_index=True, use_container_width=True)
        st.caption(
            "Responsables sugeridos; no son asignaciones ni plazos aprobados por MindTEC."
        )

    with approach_tab:
        _section("07 / ALCANCE Y PROCEDENCIA")
        if report["fuentes"]:
            visible = [{
                "Fuente": x["nombre"],
                "Procedencia": x["origen"],
                "Periodo declarado": x["periodo"],
                "Rol": x["rol"],
                "Huella SHA-256": x["sha256"],
                "Clase": "Demostración" if x["demo"] else "Fuente no demo",
            } for x in report["fuentes"]]
            st.dataframe(pd.DataFrame(visible), hide_index=True, use_container_width=True)
        else:
            st.info("Sin fuentes cargadas.")
        st.subheader("Alcance metodológico")
        st.markdown(
            "La revisión separa **integridad técnica**, **exactitud de KPI**, "
            "**conciliación de fuentes**, **representatividad de la muestra** y "
            "**gobierno del dato**. Ninguna dimensión sustituye a las demás."
        )
        st.markdown(
            "**Reservas expresas:** las fuentes documentadas de compras parciales "
            "no equivalen al mercado total; las reglas históricas de Perfect Store, "
            "SKU núcleo y frío requieren confirmación del sistema oficial; "
            "un análisis de chi-cuadrado o McNemar no calcula la confiabilidad "
            "global de un dashboard."
        )
        st.markdown(
            "**Criterio de cierre por KPI:** fuente identificada, periodo, "
            "universo, fórmula aprobada, versión, cálculo reproducible, "
            "contraste independiente y resolución de diferencias."
        )

    st.divider()
    _section("08 / ENTREGA PARA COMITÉ")
    st.markdown(
        "Descarga el informe de síntesis para revisión interna. "
        "El archivo contiene los nombres de fuentes y los hallazgos de la sesión, "
        "no copia los registros crudos. Puede seguir siendo información confidencial."
    )
    html = export_html(report).encode("utf-8")
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M")
    st.download_button(
        "Descargar informe ejecutivo HTML · listo para imprimir",
        data=html,
        file_name=f"MindTEC_Informe_Ejecutivo_{stamp}.html",
        mime="text/html",
        type="primary",
    )
    st.caption(
        "Abre el archivo local en un navegador y usa Imprimir → Guardar como PDF. "
        "No es un informe emitido, respaldado ni certificado por PwC."
    )
