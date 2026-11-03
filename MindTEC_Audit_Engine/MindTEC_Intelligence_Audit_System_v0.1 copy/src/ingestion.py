from pathlib import Path
import pandas as pd
import json
import re
import unicodedata
from difflib import get_close_matches
from datetime import datetime

CARPETA = Path("data/raw")
SALIDA = Path("data/outputs/auditoria_relacional")

ARCHIVO_DISTRIBUIDORES = "catalogo_distribuidor_2026-10-30.csv"
ARCHIVO_PRODUCTOS = "catalogo_producto_2026-10-30.csv"
def normalizar_texto(valor):

    if pd.isna(valor):
        return ""

    texto = str(valor).upper().strip()

    # Eliminar tildes.
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(
        c for c in texto
        if not unicodedata.combining(c)
    )

    # Normalizar puntuación y espacios.
    texto = re.sub(r"[^A-Z0-9]", " ", texto)
    texto = re.sub(r"\s+", " ", texto).strip()

    # Estandarizar sufijos legales SIN eliminarlos.
    sufijos = {
        " S R L": " S.R.L.",
        " SRL": " S.R.L.",
        " S A": " S.A.",
        " SA": " S.A.",
        " LTDA": " LTDA."
    }

    for sufijo, estandar in sufijos.items():
        if texto.endswith(sufijo):
            razon_social = texto[:-len(sufijo)].strip()
            texto = razon_social + estandar
            break

    return texto

def cargar_bases():
    distribuidores = pd.read_csv(
        CARPETA / ARCHIVO_DISTRIBUIDORES,
        encoding="utf-8-sig"
    )

    productos = pd.read_csv(
        CARPETA / ARCHIVO_PRODUCTOS,
        encoding="utf-8-sig"
    )

    return distribuidores, productos


def auditar_relaciones(distribuidores, productos):

    # Normalización temporal: no modifica los archivos originales.
    distribuidores["nombre_normalizado"] = (
        distribuidores["Valor"].apply(normalizar_texto)
    )

    productos["distribuidor_normalizado"] = (
        productos["Distribuidor"].apply(normalizar_texto)
    )

    nombres_distribuidores = (
        distribuidores["nombre_normalizado"]
        .dropna()
        .unique()
        .tolist()
    )

    # 1. Validación de distribuidores.
    relaciones = []

    for nombre in productos["Distribuidor"].dropna().unique():

        normalizado = normalizar_texto(nombre)

        if normalizado in nombres_distribuidores:
            estado = "COINCIDENCIA"
            sugerencia = normalizado

        else:
            candidatos = get_close_matches(
                normalizado,
                nombres_distribuidores,
                n=3,
                cutoff=0.65
            )

            estado = "REVISAR"
            sugerencia = "; ".join(candidatos)

        relaciones.append({
            "distribuidor_producto": nombre,
            "nombre_normalizado": normalizado,
            "estado": estado,
            "posibles_coincidencias": sugerencia
        })

    df_relaciones = pd.DataFrame(relaciones)

    # 2. IDs de producto repetidos.
    ids_repetidos = productos[
        productos.duplicated(subset=["ID"], keep=False)
    ].sort_values("ID")

    # 3. Nombres SKU repetidos.
    sku_repetidos = productos[
        productos.duplicated(
            subset=["Producto (SKU)"],
            keep=False
        )
    ].sort_values("Producto (SKU)")

    # 4. Productos sin distribuidor.
    sin_distribuidor = productos[
        productos["Distribuidor"].isna()
        | (productos["Distribuidor"].astype(str).str.strip() == "")
    ]

    # 5. Estado de los catálogos.
    resumen = {
        "fecha_ejecucion": datetime.now().isoformat(),

        "total_distribuidores_catalogo": int(len(distribuidores)),
        "total_productos_catalogo": int(len(productos)),

        "distribuidores_coincidentes": int(
            (df_relaciones["estado"] == "COINCIDENCIA").sum()
        ),

        "distribuidores_por_revisar": int(
            (df_relaciones["estado"] == "REVISAR").sum()
        ),

        "ids_producto_repetidos": int(
            ids_repetidos["ID"].nunique()
        ),

        "sku_repetidos": int(
            sku_repetidos["Producto (SKU)"].nunique()
        ),

        "productos_sin_distribuidor": int(len(sin_distribuidor))
    }

    return (
        resumen,
        df_relaciones,
        ids_repetidos,
        sku_repetidos,
        sin_distribuidor
    )


def ejecutar():

    SALIDA.mkdir(parents=True, exist_ok=True)

    distribuidores, productos = cargar_bases()

    resultados = auditar_relaciones(
        distribuidores,
        productos
    )

    resumen, relaciones, ids, sku, sin_distribuidor = resultados

    # Guardar resultados.
    with open(
        SALIDA / "resumen_relacional.json",
        "w",
        encoding="utf-8"
    ) as archivo:
        json.dump(
            resumen,
            archivo,
            ensure_ascii=False,
            indent=4
        )

    relaciones.to_csv(
        SALIDA / "relacion_distribuidores.csv",
        index=False,
        encoding="utf-8-sig"
    )

    ids.to_csv(
        SALIDA / "ids_repetidos.csv",
        index=False,
        encoding="utf-8-sig"
    )

    sku.to_csv(
        SALIDA / "sku_repetidos.csv",
        index=False,
        encoding="utf-8-sig"
    )

    sin_distribuidor.to_csv(
        SALIDA / "productos_sin_distribuidor.csv",
        index=False,
        encoding="utf-8-sig"
    )

    print("\n=== AUDITORÍA RELACIONAL MINDTEC ===")

    for indicador, valor in resumen.items():
        print(f"{indicador}: {valor}")

    print("\nAUDITORÍA FINALIZADA")
    print("Resultados guardados en:", SALIDA)


if __name__ == "__main__":
    ejecutar()