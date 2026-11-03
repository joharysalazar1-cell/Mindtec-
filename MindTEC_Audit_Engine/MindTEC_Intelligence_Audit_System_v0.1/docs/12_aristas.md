# Catálogo de las 12 aristas

| # | Arista | Pregunta central | Datos mínimos | Estado inicial |
|---|---|---|---|---|
| 1 | Distribución/cobertura | ¿Qué tiendas y zonas están cubiertas? | ID tienda, ubicación, canal, fecha | Parcial |
| 2 | Disponibilidad/quiebres | ¿Qué productos están presentes o agotados? | Tienda, SKU, disponibilidad/quiebre | Parcial |
| 3 | Inventario/stock | ¿Qué stock se declara por tienda-producto? | Tienda, SKU, stock/estado, fecha | Por validar |
| 4 | Precios | ¿A qué precio se ofrece cada SKU? | Tienda, SKU, precio, fecha | Parcial |
| 5 | Competencia/participación | ¿Cómo se distribuye la presencia entre marcas? | Universo, marca, medida y denominador | Por definir |
| 6 | Cadencia temporal | ¿Cómo cambian los indicadores en el tiempo? | Fechas comparables y periodos | Parcial |
| 7 | Portafolio/surtido | ¿Qué amplitud de productos maneja cada tienda? | Tienda, SKU, categoría, marca | Parcial |
| 8 | Rendimiento comercial | ¿Qué ventas/volúmenes/valores se registran? | Facturas/transacciones, cantidades, valores | Pendiente base de facturas |
| 9 | Calidad/confiabilidad | ¿Qué tan íntegros y consistentes son los datos? | Todas las fuentes + reglas | En implementación |
| 10 | Metodología | ¿Qué se puede afirmar del diseño y cobertura? | Diseño, marco, muestra, cuotas, ponderadores | No verificable sin documentación |
| 11 | Predicción/modelos | ¿Qué resultados futuros pueden estimarse? | Historia suficiente, objetivo y variables | No habilitado |
| 12 | Predicción operativa tienda-producto | ¿Dónde priorizar visitas/reposición? | Panel tienda-SKU-tiempo y resultados | No habilitado |

**Regla:** “Parcial”, “pendiente” o “no verificable” no significa que la dimensión sea inútil; significa que no se debe fabricar un indicador sin los datos y definiciones requeridos.
