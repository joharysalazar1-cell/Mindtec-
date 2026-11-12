# Dashboard HTML de auditoría MindTEC

Código de la vista visual con los 12 KPI, filtros por marca/mes/categoría, comparación de competidores, controles documentales por distribuidor y trazabilidad directa. El generador produce un HTML autónomo que funciona localmente sin servidor ni instalación de librerías.

## Qué incorpora esta actualización

- Tarjetas con publicación, resultado disponible y tipo de respaldo.
- Distinción entre auditoría conservada, reconstrucción operativa, reproducción aritmética del panel y cálculo pendiente.
- Matriz de todas las marcas y los 12 KPI; gráficos con categoría, mes, unidades y escala comunes entre páginas.
- Trazabilidad `KPI → fórmula → universo relacionado → variables → registro normalizado / factura → fila original`.
- Consulta de los campos completos de la visita y la factura, referencias utilizadas por el cálculo y exportación JSON/CSV.
- Fichas recuperadas, configuración observada, requisitos pendientes, fuentes y huellas de origen.

Los resultados publicados no se sobrescriben. El universo relacionado no se atribuye automáticamente al numerador de cada componente. Una reproducción con entradas del panel no se convierte en auditoría independiente.

## Datos privados y construcción local

Este repositorio es público. Solo contiene código y documentación: las facturas, visitas, JSON privados y HTML con datos incrustados no se distribuyen aquí. No active GitHub Pages para publicar esos resultados privados.

Requiere Python 3.10+ para construir y Node.js 20+ para las comprobaciones; no necesita paquetes externos. Desde la raíz del repositorio:

```powershell
python dashboard-html/build.py --data-dir "C:/ruta/privada/auditoria"
```

La carpeta privada debe contener los tres insumos ya generados por la auditoría:

1. `executive-data.json`: resultados, métodos, controles documentales y configuración observada.
2. `MindTEC_KPI_originales_restaurados.html`: base histórica conservada de visitas, registros e ítems de factura.
3. `Exportacion_KPI_disponibles_2026-11-12/resultados_12_KPI.json`: referencias explícitas utilizadas por cada cálculo operativo.

El generador incorpora los datos privados en `dashboard-html/dist/MindTEC_Dashboard_con_auditoria_y_trazabilidad.html` y genera un ZIP en la misma carpeta. `dist/` está excluido de Git. No es una conexión en vivo ni recalcula automáticamente la base cuando cambia el servidor: el proceso integra el corte preparado y conserva su procedencia.

## Verificación

```powershell
node dashboard-html/test-source.cjs
node dashboard-html/test-dashboard.cjs
node dashboard-html/test-trace.cjs
```

Los dos últimos comandos requieren el HTML construido. Admiten una ruta alternativa como primer argumento y sus expectativas corresponden al corte septiembre/octubre de 2026. Comprueban filtros y separación de fuentes, detalles de los KPI, variables y claves de origen. La prueba de fuente no necesita datos privados.

En el corte local se verificaron 633 vistas, 1.320 detalles KPI, 54 fichas, 25 distribuidores, 110 grupos y 5.940 insumos. Las referencias repetidas entre cálculos incluyen 110.534 referencias a campos y 101.223 referencias a líneas de factura; no son registros únicos adicionales. Las pruebas funcionales no sustituyen la inspección visual del HTML en el navegador.

## Limitaciones que siguen visibles

La configuración actual de cliente no demuestra la vigencia histórica por marca/canal/mes. Los pesos, aplicabilidad, exclusiones y componentes que la plataforma no exportó siguen identificados como pendientes. Las facturas documentan compras parciales, no ventas ni mercado total. El piloto no acredita una muestra probabilística de toda La Paz.

El cierre de validación integral requiere acreditar fuente, regla, universo, independencia, versión, exactitud y coincidencia para cada resultado. Esta interfaz hace visibles esos requisitos; no los reemplaza por un porcentaje de confianza inventado.
