import pandas as pd
from pathlib import Path

# ==========================================
# MINDTEC AUDIT ENGINE
# MODULO 01: DATA INSPECTOR
# ==========================================

BASE_DIR = Path(__file__).resolve().parent

ARCHIVO = BASE_DIR / "data" / "raw" / "base_prueba.csv"

# Cargar base
# Verificar existencia del archivo
if not ARCHIVO.exists():
    raise FileNotFoundError(
        f"No se encontró el archivo: {ARCHIVO}"
    )

# Verificar que tenga contenido
if ARCHIVO.stat().st_size == 0:
    raise ValueError(
        "El archivo existe, pero está vacío."
    )

# Cargar base
# Verificar existencia del archivo
if not ARCHIVO.exists():
    raise FileNotFoundError(
        f"No se encontró el archivo: {ARCHIVO}"
    )

# Verificar que tenga contenido
if ARCHIVO.stat().st_size == 0:
    raise ValueError(
        "El archivo existe, pero está vacío."
    )

# Cargar base
df = pd.read_csv(ARCHIVO)
print("\n========== AUDITORÍA DE DATOS ==========\n")

# 1. Dimensiones
print("FILAS:", df.shape[0])
print("COLUMNAS:", df.shape[1])

# 2. Variables
print("\nVARIABLES:")
print(df.columns.tolist())

# 3. Tipos de datos
print("\nTIPOS DE DATOS:")
print(df.dtypes)

# 4. Valores faltantes
print("\nVALORES FALTANTES:")
print(df.isnull().sum())

# 5. Registros duplicados exactos
print("\nDUPLICADOS EXACTOS:")
print(df.duplicated().sum())

# 6. Estadísticas descriptivas
print("\nESTADÍSTICAS:")
print(df.describe(include="all"))

# 7. Alertas de precios
print("\nALERTAS DE PRECIO:")

precios_sospechosos = df[
    (df["precio_bs"] <= 0) |
    (df["precio_bs"] > 30)
]

print(precios_sospechosos)
# 8. Resumen estadístico por marca y producto
print("\nRESUMEN DE PRECIOS POR MARCA Y PRODUCTO:")

resumen = (
    df.groupby(["marca", "producto"], dropna=False)
      .agg(
          n_registros=("precio_bs", "size"),
          n_precios_validos=("precio_bs", "count"),
          media=("precio_bs", "mean"),
          mediana=("precio_bs", "median"),
          minimo=("precio_bs", "min"),
          maximo=("precio_bs", "max"),
      )
      .reset_index()
)

# Calcular precios faltantes
resumen["n_precios_faltantes"] = (
    resumen["n_registros"] - resumen["n_precios_validos"]
)

# Mostrar resultados
print(resumen.to_string(index=False))

# 9. Exportar resultados
OUTPUTS = BASE_DIR / "data" / "outputs"
OUTPUTS.mkdir(parents=True, exist_ok=True)

archivo_salida = OUTPUTS / "resumen_precios_por_producto.csv"

resumen.to_csv(
    archivo_salida,
    index=False,
    encoding="utf-8-sig"
)

print(f"\nResumen exportado a: {archivo_salida}")
# 10. Distribución de registros por tienda

print("\nDISTRIBUCIÓN DE REGISTROS POR TIENDA:")

distribucion_tiendas = (
    df.groupby("id_tienda")
      .size()
      .reset_index(name="n_registros")
      .sort_values("n_registros", ascending=False)
)

distribucion_tiendas["participacion_pct"] = (
    distribucion_tiendas["n_registros"] /
    distribucion_tiendas["n_registros"].sum()
) * 100

print(distribucion_tiendas.to_string(index=False))
print("\n========== FIN DE AUDITORÍA ==========")
