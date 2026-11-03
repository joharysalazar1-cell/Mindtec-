from pathlib import Path
from datetime import datetime, timezone
import hashlib, json, re
import pandas as pd
import numpy as np

VERSION = "0.1.0"

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def read_source(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        # autodetección de separador común; no se modifica el archivo original
        try:
            return pd.read_csv(path, low_memory=False)
        except UnicodeDecodeError:
            return pd.read_csv(path, encoding="latin-1", low_memory=False)
    if suffix in (".xlsx", ".xlsm"):
        return pd.read_excel(path)
    raise ValueError("Formato no soportado. Usa CSV, XLSX o XLSM.")

def profile_frame(df: pd.DataFrame):
    cols = []
    for c in df.columns:
        s = df[c]
        non_null = s.dropna()
        examples = [str(x)[:100] for x in non_null.astype(str).drop_duplicates().head(3)]
        cols.append({
            "variable": str(c),
            "dtype": str(s.dtype),
            "n_faltantes": int(s.isna().sum()),
            "pct_faltantes": round(float(s.isna().mean() * 100), 2),
            "n_unicos": int(s.nunique(dropna=True)),
            "ejemplos": " | ".join(examples)
        })
    return pd.DataFrame(cols)

def create_issues(df: pd.DataFrame) -> pd.DataFrame:
    issues = []
    n = len(df)
    missing_cells = int(df.isna().sum().sum())
    if missing_cells:
        issues.append(["CALIDAD-001", "Faltantes", "INFO", f"{missing_cells} celdas vacías en {n} filas.", "Revisar según obligatoriedad de cada campo."])
    dup = int(df.duplicated().sum())
    if dup:
        issues.append(["CALIDAD-002", "Duplicados exactos", "ALERTA", f"{dup} filas exactamente duplicadas.", "Determinar si son duplicados reales o registros repetidos legítimos."])
    for col in df.columns:
        name = str(col).strip().lower()
        if any(k in name for k in ["precio", "monto", "importe", "valor"]):
            s = pd.to_numeric(df[col], errors="coerce")
            if s.notna().any():
                zero = int((s == 0).sum())
                neg = int((s < 0).sum())
                if zero:
                    issues.append(["VALOR-001", f"{col}: ceros", "ALERTA", f"{zero} registros con valor cero.", "Confirmar si cero es válido, ausencia o error de captura."])
                if neg:
                    issues.append(["VALOR-002", f"{col}: negativos", "ALERTA", f"{neg} registros negativos.", "Validar regla de negocio y unidad."])
                if s.notna().sum() >= 4:
                    q1, q3 = s.quantile([.25, .75])
                    iqr = q3 - q1
                    if iqr > 0:
                        out = int(((s < q1 - 1.5*iqr) | (s > q3 + 1.5*iqr)).sum())
                        if out:
                            issues.append(["VALOR-003", f"{col}: posibles atípicos", "REVISAR", f"{out} valores fuera de 1.5*IQR.", "No eliminar automáticamente; contrastar con evidencia y contexto."])
    return pd.DataFrame(issues, columns=["codigo", "dimension", "severidad", "evidencia", "accion_recomendada"])

def run_profile(source: Path) -> Path:
    source = source.expanduser().resolve()
    if not source.exists():
        raise FileNotFoundError(f"No existe el archivo: {source}")
    df = read_source(source)
    if df.empty or len(df.columns) == 0:
        raise ValueError("El archivo no contiene registros/columnas legibles.")
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = Path("data/outputs") / run_id
    out.mkdir(parents=True, exist_ok=True)

    col_profile = profile_frame(df)
    issues = create_issues(df)
    cat_cols = [c for c in df.columns if df[c].dtype == "object" and df[c].nunique(dropna=True) <= 100]
    cats = []
    for c in cat_cols:
        vc = df[c].fillna("[VACÍO]").astype(str).value_counts().head(30)
        for value, count in vc.items():
            cats.append({"variable": str(c), "valor": value, "frecuencia": int(count)})
    pd.DataFrame(cats, columns=["variable", "valor", "frecuencia"]).to_csv(out / "category_profile.csv", index=False, encoding="utf-8-sig")
    col_profile.to_csv(out / "column_profile.csv", index=False, encoding="utf-8-sig")
    issues.to_csv(out / "issues.csv", index=False, encoding="utf-8-sig")

    numeric = df.select_dtypes(include=np.number)
    summary = {
        "version": VERSION, "run_id": run_id,
        "source_file": source.name, "source_sha256": sha256_file(source),
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "rows": int(df.shape[0]), "columns": int(df.shape[1]),
        "exact_duplicate_rows": int(df.duplicated().sum()),
        "missing_cells": int(df.isna().sum().sum()),
        "variables": [str(c) for c in df.columns],
        "numeric_describe": json.loads(numeric.describe().to_json()) if len(numeric.columns) else {},
        "notes": [
            "Perfil técnico preliminar; no certifica validez metodológica.",
            "No se imputaron, eliminaron ni modificaron registros.",
            "Las alertas requieren validación humana."
        ]
    }
    (out / "profile.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {
        "run_id": run_id, "source": str(source), "sha256": summary["source_sha256"],
        "software_version": VERSION, "rows": int(len(df)), "columns": int(len(df.columns))
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return out.resolve()
