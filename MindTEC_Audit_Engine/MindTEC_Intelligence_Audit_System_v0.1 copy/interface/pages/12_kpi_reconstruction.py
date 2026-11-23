"""Review 12 commercial KPIs from a locally reconstructed historical CSV.

Only reads a user-provided CSV or a pre-approved file inside data/processed.
Does not reconstruct official backend metrics, contact APIs or modify sources.
"""
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
LOCAL_FILE = ROOT / "data" / "processed" / "MindTEC_Matriz_Reconstruccion_2184_KPI.csv"

REQUIRED = {
    "mes", "empresa", "categoria", "marca", "indicador",
    "publicado_texto", "reconstruccion_anterior", "recalculado_fuentes",
    "verificacion_recalculado", "escenario_no_oficial", "clasificacion",
    "evidencia_historica", "pendiente_para_certificar"
}

def _read(source):
    frame = pd.read_csv(source, encoding="utf-8-sig", dtype="string", keep_default_na=False)
    missing = REQUIRED - set(frame.columns)
    if missing:
        raise ValueError("Faltan columnas de auditoría requeridas: " + ", ".join(sorted(missing)))
    keys = ["mes", "empresa", "categoria", "marca", "indicador"]
    if frame.duplicated(keys).any():
        raise ValueError("Hay claves duplicadas mes×empresa×categoría×marca×indicador. No se atribuyen valores ambiguos.")
    for name in ("reconstruccion_anterior", "recalculado_fuentes", "escenario_no_oficial"):
        frame[name] = pd.to_numeric(frame[name].replace("", pd.NA), errors="coerce")
    return frame


def _counts(frame):
    has_calc = frame["recalculado_fuentes"].notna()
    return (
        len(frame),
        int(has_calc.sum()),
        int((frame["verificacion_recalculado"] == "Reproducción numérica coincide").sum()),
        int((frame["verificacion_recalculado"] == "Diferencia con auditoría conservada").sum()),
    )


def render():
    st.title("Reconstrucción integral · 12 KPI")
    st.caption("Informe histórico: cifras publicadas, auditoría conservada y recálculo de fuentes. Los escenarios no oficiales se muestran por separado.")
    st.warning(
        "Este módulo NO garantiza exactitud oficial ni actualiza los 12 indicadores desde una API. "
        "La matriz utiliza evidencia histórica preparada localmente; no incluye reglas backend ausentes."
    )
    uploaded = st.file_uploader(
        "Importar matriz de reconstrucción CSV",
        type=["csv"],
        key="kpi_reconstruction_csv"
    )
    if uploaded is None and not LOCAL_FILE.is_file():
        st.info(
            "Descarga la matriz reconstruida y cárgala aquí, o copia el archivo "
            "MindTEC_Matriz_Reconstruccion_2184_KPI.csv en data/processed del proyecto. "
            "No subas el archivo privado al repositorio público."
        )
        return
    try:
        df = _read(uploaded if uploaded is not None else LOCAL_FILE)
    except (ValueError, OSError, UnicodeDecodeError) as exc:
        st.error(f"No se pudo validar la matriz: {exc}")
        return
    if df.empty:
        st.warning("La matriz no contiene resultados.")
        return

    cells, recalcs, matched, differences = _counts(df)
    a, b, c, d = st.columns(4)
    a.metric("Resultados del catálogo", cells)
    b.metric("Recálculos de fuentes", recalcs)
    c.metric("Coincidencias con auditoría previa", matched)
    d.metric("Diferencias por revisar", differences)
    st.caption(
        "La concordancia es interna respecto a reconstrucciones históricas conservadas. "
        "No equivale a tasa de confianza, exactitud oficial ni muestra representativa."
    )

    by = (df.groupby("indicador", dropna=False)
          .agg(combinaciones=("marca", "size"),
               recálculos=("recalculado_fuentes", "count"),
               escenarios_no_oficiales=("escenario_no_oficial", "count"))
          .reset_index())
    st.subheader("Cobertura por indicador")
    st.dataframe(by, hide_index=True, use_container_width=True)
    st.bar_chart(by.set_index("indicador")[["recálculos", "escenarios_no_oficiales"]], horizontal=True)

    st.subheader("Análisis por periodo, marca y categoría")
    x, y, z = st.columns(3)
    with x: period = st.multiselect("Periodo", sorted(df["mes"].unique().tolist()), default=sorted(df["mes"].unique().tolist()))
    with y: metric = st.multiselect("Indicador", sorted(df["indicador"].unique().tolist()), default=sorted(df["indicador"].unique().tolist()))
    with z: category = st.multiselect("Categoría", sorted(df["categoria"].unique().tolist()))
    search = st.text_input("Buscar marca o empresa", placeholder="Ej.: Coca-Cola, CBN")
    allowed = df["mes"].isin(period) & df["indicador"].isin(metric)
    if category: allowed &= df["categoria"].isin(category)
    if search.strip():
        allowed &= (
            df["marca"].str.contains(search, case=False, regex=False)
            | df["empresa"].str.contains(search, case=False, regex=False)
        )
    selection = df.loc[allowed].copy()
    st.caption(f"{len(selection)} combinaciones dentro del alcance.")
    columns = [
        "mes", "empresa", "categoria", "marca", "indicador",
        "publicado_texto", "reconstruccion_anterior", "recalculado_fuentes",
        "verificacion_recalculado", "escenario_no_oficial",
    ]
    st.dataframe(selection[columns], hide_index=True, use_container_width=True)
    st.download_button(
        "Exportar alcance CSV",
        selection.to_csv(index=False).encode("utf-8-sig"),
        file_name="MindTEC_reconstruccion_KPI_filtrada.csv",
        mime="text/csv",
    )
    if selection.empty:
        return
    with st.expander("Consultar fórmula, evidencia y asuntos pendientes"):
        options = list(selection.index)
        selected_index = st.selectbox(
            "Combinación a inspeccionar",
            options,
            format_func=lambda i: (
                f"{selection.loc[i,'mes']} · {selection.loc[i,'marca']} "
                f"· {selection.loc[i,'indicador']}"
            ),
        )
        row = selection.loc[selected_index]
        st.markdown("**Fórmula / método de recálculo**")
        st.write(row.get("formula_reconstruccion", "No documentado"))
        st.markdown("**Referencia a evidencia preservada**")
        st.write(row.get("evidencia_historica", "No documentada"))
        st.markdown("**Pendiente para la certificación**")
        st.write(row.get("pendiente_para_certificar", "No documentado"))
        st.markdown("**Observación actual**")
        st.write(row.get("observacion_recalculo", "") or "Sin observación adicional registrada.")
        st.caption("Las simulaciones se presentan exclusivamente como escenarios de sensibilidad.")
