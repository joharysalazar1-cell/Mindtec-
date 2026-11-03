# MindTEC Intelligence & Audit System — v0.1

Sistema independiente para auditar, analizar y reconciliar datos de retail. No reemplaza el dashboard de MindTEC: verifica sus resultados con cálculos reproducibles.

## Estado
Esta versión implementa la base del proyecto y el primer diagnóstico automatizado de archivos. No calcula todavía indicadores comerciales definitivos: antes se debe confirmar el diccionario de datos, las reglas de negocio y el universo de tiendas/SKU.

## Las 12 aristas analíticas
1. **Distribución y cobertura:** tiendas, zonas, canales y cobertura observada.
2. **Disponibilidad y quiebres:** presencia de productos y quiebres reportados.
3. **Inventario y stock:** stock declarado y señales de agotamiento; no equivale a inventario físico.
4. **Precios:** precios por SKU, tienda, marca y presentación.
5. **Competencia y participación:** presencia/participación por marca; definir denominador antes de calcular share.
6. **Cadencia temporal:** evolución por fecha/periodo y consistencia temporal.
7. **Portafolio y surtido:** amplitud, variedad y composición del surtido.
8. **Rendimiento comercial:** ventas, volumen, valor y Sell-in cuando exista una base transaccional válida.
9. **Calidad y confiabilidad:** faltantes, duplicados, valores atípicos, integridad y trazabilidad.
10. **Metodología:** cobertura del diseño, cumplimiento de cuotas/muestra y limitaciones; solo verificable con documentación metodológica.
11. **Predicción y modelos:** modelos estadísticos/ML cuando haya suficiente historia, variables y objetivo medible.
12. **Predicción operativa tienda-producto:** alertas/priorización por tienda y SKU; requiere historia longitudinal suficiente.

## Arquitectura
- **Capa 1 — Determinística:** Python/Pandas; cálculos, reglas, validaciones y conciliaciones. Fuente de verdad numérica.
- **Capa 2 — Estadística/analítica:** inferencia, segmentación y modelos, únicamente cuando los datos lo permitan.
- **Capa 3 — IA interpretativa:** explica resultados estructurados y redacta hallazgos. Nunca inventa cifras ni modifica datos.

## Fuentes previstas
- Captura de tiendas y productos multicategoría (actualmente disponible como `base_limpia.csv`).
- Export/control de envíos Kobo (metadatos de envíos; no confundir con la base detallada de tiendas/productos).
- Base de facturas (pendiente de limpieza/entrega).
- Export de indicadores del dashboard (para reconciliación, cuando se comparta).

## Instalación Windows
1. Extrae el ZIP.
2. Abre la carpeta en VS Code.
3. En terminal PowerShell:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   python -m pip install -r requirements.txt
   ```
4. Copia una base CSV/XLSX a `data/raw/`.
5. Ejecuta:
   ```powershell
   python main.py --file data/raw/base_limpia.csv
   ```

## Salidas
Los resultados se guardan en `data/outputs/<run_id>/`:
- `profile.json`: perfil técnico del archivo.
- `column_profile.csv`: faltantes, únicos, tipos y ejemplos por variable.
- `category_profile.csv`: frecuencias de variables categóricas seleccionadas.
- `issues.csv`: alertas de calidad no corregidas automáticamente.
- `run_manifest.json`: archivo fuente, hash SHA-256, fecha y versión.

## Reglas no negociables
- Los archivos originales no se modifican.
- Ningún valor se corrige o imputa silenciosamente.
- Un valor atípico es una alerta, no un error confirmado.
- No calcular participación de mercado sin definir numerador, denominador, universo y ponderación.
- No afirmar representatividad sin diseño muestral/documentación.
- Diferencias contra el dashboard se clasifican: coincidencia exacta, diferencia explicada, diferencia no explicada, error confirmado o no verificable.
