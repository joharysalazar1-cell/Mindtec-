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


## Diferencias, sesgo, MAE y RMSE

La sección Estadística compara publicación y auditoría histórica (o cálculo operativo con sus límites) usando Δ = D − C, sesgo = media(Δ), MAE = media(|Δ|) y RMSE = raíz(media(Δ²)). Conserva grupos de un KPI, categoría y mes; no promedia unidades distintas. Incluye número de pares, diferencias de cada marca, fórmulas y trazabilidad. Las reproducciones aritméticas del panel se excluyen del comparador operativo para evitar circularidad. Son estadísticos descriptivos, no porcentajes de confianza.

## Chi-cuadrado y presencia pareada

Septiembre y octubre observan las mismas tiendas. Se utiliza McNemar para presencia binaria pareada, con χ² = (b−c)²/(b+c), gl = 1 y p exacto bilateral binomial como principal. El p asintótico se muestra únicamente con al menos 25 discordantes como regla conservadora de implementación. No se usa Pearson para tratar las dos visitas de una tienda como independientes ni se fabrican conteos a partir de porcentajes publicados.

Los grupos incluyen solo stickers únicos, presencia binaria y elegibilidad en ambos meses. Se muestran la tabla 2×2, las exclusiones y las variables de cada tienda. Holm ajusta la familia completa antes de filtrar. En el corte actual hay 43 grupos pareados; las pruebas no se extienden a los 12 KPI sin sus conteos oficiales. La interpretación es exploratoria: supone tiendas independientes entre sí y medición equivalente entre olas; no prueba causalidad ni representatividad de ciudad.

Referencias: [McNemar en statsmodels](https://www.statsmodels.org/stable/generated/statsmodels.stats.contingency_tables.mcnemar.html) y [chi-cuadrado de Pearson en NIST](https://www.itl.nist.gov/div898/software/dataplot/refman1/auxillar/chistest.htm).

Comprobaciones adicionales:

```powershell
node dashboard-html/test-statistics-core.cjs
node dashboard-html/test-statistics-dashboard.cjs
```

La primera verifica métricas, casos límite, p exactos y ajuste Holm sin datos privados. La segunda requiere el HTML local construido. Los 43 conteos pareados, p exactos y ajustes Holm se contrastaron además con una implementación independiente en Python; la cola χ² de un grado de libertad se contrastó con `math.erfc`.


## Vistas mensual, anual y total

Los controles propios de Estadística permiten elegir vista mensual (un mes o todos los meses disponibles), anual o total, además de año, KPI, categoría y conjunto de marcas. Sustituyen el filtro de mes superior solo en esta sección. El resto del dashboard conserva sus filtros.

Los resúmenes anuales y totales agrupan los pares marca×mes originales y recalculan sesgo, MAE y RMSE desde sus diferencias. No promedian RMSE mensuales ni reconstruyen el KPI comercial anual. Cada par pesa una vez; las marcas pueden repetirse entre meses, por lo que el resumen sigue siendo descriptivo. Se muestra la cobertura real: para 2026 solo están disponibles septiembre y octubre.

El gráfico temporal usa un solo KPI y categoría; conserva signo, unidades, base de pares y huecos sin imputar. Con un solo año se muestran puntos sin sugerir tendencia interanual. La vista total conserva la evolución mensual y añade el resumen acumulado. El gráfico de diferencias muestra hasta 20 pares de mayor discrepancia absoluta, con acceso al origen y CSV completo.

McNemar conserva la comparación pareada septiembre/octubre; no se suman sus p-valores o estadísticos para crear un resultado anual/total.

```powershell
node dashboard-html/test-periods.cjs
```

La prueba verifica seis combinaciones de periodo/comparador, fórmulas sobre pares originales, cobertura, filtros temporales propios y equivalencia anual/total cuando solo hay un año.


## Inventario de datos y filtros sin falsos ceros

Al cambiar de marca se ajusta una categoría incompatible con sus publicaciones, conservando el mes para no ocultar falta de cobertura temporal. La vista distingue filas KPI publicadas, productos documentados y registros de colecta. Si no existe denominador de contraste, muestra «No evaluable» en lugar de 0/0.

El panel Datos existentes lista SKU, productos, meses y filas de origen. La disponibilidad histórica ignora el mes/categoría activos y se identifica expresamente. Una marca con facturas pero sin KPI publicado conserva su evidencia sin recibir porcentajes de otra marca. En Aloe se conservan los nombres de cada fuente y se muestran coincidencias para revisión, sin homologar automáticamente Aloe Vera Premium, Aloe Tai, La Case, Original HB o Tai.

```powershell
node dashboard-html/test-filters.cjs
node dashboard-html/test-aloe.cjs
```

Las pruebas comprueban cambio de categoría en las 64 marcas con publicación, presencia documental sin KPI y siete combinaciones de marca/mes relacionadas con Aloe. Las pruebas requieren el corte privado local.


## Todas las marcas disponibles

El selector y la tabla de catálogo reúnen todos los nombres no vacíos del panel publicado, la colecta normalizada, las marcas originales y analíticas de factura, los KPI históricos y los grupos de insumos. El corte contiene 175 nombres registrados, incluidas variantes de escritura; no se afirma que sean 175 marcas homologadas distintas. Cada nombre conserva procedencia, meses y conteos de registros. La búsqueda de factura puede coincidir con su marca original o analítica, sin transferir KPI entre etiquetas distintas. Una marca sin publicación conserva sus datos fuente.

Verificar con `node dashboard-html/test-all-brands.cjs` después de construir el HTML local.


## Perfect Store por tienda

El dashboard incorpora un corte operativo preparado de Perfect Store en sus tarjetas y una sección propia. Los filtros de marca, categoría y mes se sincronizan con el explorador de componentes y preguntas originales, integrado en el HTML sin conexión. Los datos y resultados históricos permanecen intactos: la reconstrucción nueva muestra su fecha, su naturaleza operativa y las diferencias con el panel de ese corte. No convierte pendientes en cero ni aplica resultados a marcas documentadas exclusivamente en facturas.

El cálculo por tienda divide cumplimientos entre componentes aplicables. El resultado de marca promedia puntajes de tiendas elegibles. Una respuesta pendiente impide declarar completo el resultado; un componente no aplicable se excluye del denominador. El código conserva la regla de SKU núcleo y acceso al frío como operativas: la configuración actual no certifica su vigencia histórica.

Para incluir el módulo, prepare en la carpeta privada `Perfect_Store_reconstruido_2026-11-13/resumen_por_marca_mes.json` y `MindTEC_Perfect_Store_reconstruido.html`. `build_perfect_store_report.py --data-dir RUTA_PRIVADA` construye el explorador a partir del detalle, resumen, manifiesto y reglas privados preparados. Después ejecute `build.py --data-dir RUTA_PRIVADA` y `node dashboard-html/test-perfect-store.cjs`. La integración es opcional cuando no existe ese corte.

`reconstruct_perfect_store.py --data-dir RUTA_PRIVADA --downloads-dir RUTA_EXPORTACIONES` permite volver a preparar el corte con los cuestionarios y Excel de Scan, cubos mensuales y capturas oficiales conservadas. Requiere también la configuración observada, el universo de exclusiones aprobado, la base histórica y el archivo privado `captura_panel_perfect_store.json` con los comparadores capturados. Los códigos SKU entre versiones no se homologan por coincidencia numérica. Los IDs internos del Excel no se confunden con envioKobo.

Solo se publican generadores, plantillas vacías, lógica y pruebas. No se suben cuestionarios, capturas con resultados, ubicaciones, identificadores de visitas, archivos fuente ni HTML generados.
