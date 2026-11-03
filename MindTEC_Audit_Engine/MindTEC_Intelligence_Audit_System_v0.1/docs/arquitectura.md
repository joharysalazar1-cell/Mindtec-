# Arquitectura y criterios

## Tres capas
1. Determinística: ingestión, validación, reglas, transformaciones aprobadas, indicadores y reconciliación.
2. Estadística: intervalos, contrastes, regresiones, segmentación y modelos predictivos con supuestos documentados.
3. IA: explicación, preguntas en lenguaje natural y redacción. Solo consume resultados estructurados.

## Reconciliación contra MindTEC
Cada indicador se compara solo después de alinear periodo, universo de tiendas, SKU, duplicados, filtros, denominador, nulos/ceros y ponderación. Clasificaciones:
- Coincidencia exacta
- Diferencia explicada
- Diferencia no explicada
- Error confirmado
- No verificable

## Gobernanza
- Fuente original inmutable.
- Hash SHA-256 por archivo.
- Registro de ejecución, versión y reglas.
- No imputar ni borrar sin aprobación.
- Separar evidencia, interpretación y recomendación.
- MCP/API inicialmente de solo lectura y con permisos mínimos.
