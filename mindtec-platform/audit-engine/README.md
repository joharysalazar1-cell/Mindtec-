# Motor continuo de auditoría MindTEC

Motor de lectura y control de calidad de datos con fuentes inmutables, reglas versionadas, bitácora verificable y revisión humana. Una señal no demuestra fraude ni provoca correcciones o sanciones automáticas. No se puntúan personas ni se infiere duración de una encuesta a partir de su fecha de envío.

## Requisitos y comprobaciones

Python 3.10 o posterior y biblioteca estándar. Los contrastes JavaScript requieren Node.js. La protección nativa de procesos y la instalación de tareas se prueban en Windows; sus pruebas se omiten en otros sistemas.

```powershell
cd audit-engine
python -m unittest -v
```

Las pruebas usan datos sintéticos. Los datos reales, informes, XLSX, imágenes, configuraciones activas, credenciales y bases de ejecución se mantienen fuera del repositorio. Las plantillas JSON no contienen exclusiones reales ni secretos.

## Colecta Scan

Prepare una exportación completa con `envios`, `total` y respuestas `ruta`/`valor`, más una política derivada de `policy.example.json`. Las exclusiones necesitan ID, motivo y evidencia.

La carga JSON manual rechaza claves repetidas en cualquier nivel, incluidas claves equivalentes mediante escapes Unicode, y números no finitos o desbordados. No selecciona silenciosamente el último valor. El observador conserva los bytes rechazados y la última aceptación válida. Un Excel de encuestas o de resultados no sustituye este contrato JSON: requiere un adaptador y un cotejo explícitos antes de alimentar este motor. El adaptador XLSX de facturas tiene un alcance diferente.

```powershell
python engine.py run --runtime private/scan-runtime --source private/scan.json --policy private/policy.json
python engine.py watch --runtime private/scan-runtime --source private/scan.json --policy private/policy.json --interval 10
python engine.py verify --runtime private/scan-runtime
python report.py --runtime private/scan-runtime --output private/informe.html
```

Controles: claves duplicadas, respuestas incompatibles, contradicciones de categoría, conteos inválidos, GPS fuera de dominio e identificador de tienda ausente. Las marcas enumeradas en frío con cero caras se tratan como información que requiere interpretar la definición del formulario; no se convierten en presencia positiva ni en acusaciones.

## Comparación de colectas entre cortes

`scan_compare.py` recibe uno o varios JSON completos por lado, para admitir archivos separados por mes. Los meses se declaran explícitamente. Si falta un mes solicitado en cualquiera de los lados, detiene la comparación: no convierte una exportación parcial en supuestos borrados. Un mes presente todavía no demuestra que estén todas sus visitas; las ausencias se etiquetan como diferencias de presencia entre archivos, sujetas a confirmar filtros y cobertura.

```powershell
python scan_compare.py --previous private/corte-anterior.json --current private/septiembre.json private/octubre.json --months 2026-09 2026-10 --runtime private/comparacion-colectas
```

Para una vista mensual, declare solo ese mes; para la conjunta, declare ambos. Empareja por formulario original e ID Kobo, sin unir por tienda ni elegir entre claves o rutas duplicadas. Conserva índices del archivo, registro y respuesta, los valores antes/después y la distinción entre ausente, nulo, número y texto. Compara también los metadatos de revisión del registro. Un movimiento de mes de la misma identidad se distingue de una alta o ausencia.

La bitácora conserva los bytes de todos los archivos y el código exacto utilizado. Repetir los mismos insumos y meses recupera la aceptación existente. Límites: 24 archivos, 60 MB por archivo, 200 MB en conjunto y 100.000 señales; excederlos produce rechazo sin una aceptación truncada. Las rutas de entrada deben estar fuera del runtime. El módulo compara todos los registros, incluso excluidos históricamente, para no ocultar cambios detrás de una exclusión; no modifica la cohorte, los KPI, los originales ni las decisiones humanas. Sus señales no acreditan fraude.

`test_scan_compare.py` cubre alcance parcial, identidades ambiguas, separación por formulario, valores tipados, movimiento de mes, referencias de evidencia, custodia, cambios de implementación e idempotencia. Este comparador se ejecuta por comando; su incorporación a un observador y a la interfaz son pasos separados. Los Excel requieren un adaptador validado antes de sustituir el contrato JSON.

`scan_compare_watch.py` observa exclusivamente las ejecuciones Scan ya aceptadas en una custodia verificada, sin leer la entrada mutable ni descargar datos. La primera aceptación es `baseline_only`: conserva el corte y sus conteos mensuales, sin simular una comparación. Al aceptar Scan un contenido diferente, calcula un paquete con vista conjunta y vistas por mes contra el último contenido aceptado por este observador. Un cambio de política o código que mantenga los mismos bytes de origen no se etiqueta como cambio de datos.

```powershell
python scan_compare_watch.py --scan-runtime private/scan-runtime --runtime private/comparison-runtime --months 2026-09 2026-10 --interval 30
```

La custodia de comparación debe estar separada. El bloqueo impide observadores duplicados; un runtime queda vinculado al origen y meses iniciales. Verifica fuentes y salida aun sin cambios y recupera su aceptación después de reiniciar. Ante un mes ausente, una fuente dañada o un fallo, conserva la aceptación anterior e informa degradación. Los candidatos rechazados y el código del observador se conservan por huella. `comparison_custody_verified` acredita custodia local; no implica descarga reciente ni verificación de la plataforma externa. Las señales de la vista conjunta y de los meses se solapan y no se suman como errores independientes.

El trabajo supervisado `kind: scan_comparison` requiere `scan_runtime`, `runtime`, `months` e `interval` (10–3.600 segundos). Se enlaza con exactamente un observador Scan configurado y usa un script fijo. El estado supervisado conserva la distinción entre línea base, comparación disponible y comparación no actualizada. `test_scan_compare_watch.py` verifica recuperación, alcance incompleto, entradas mutables, cambios sin datos nuevos, corrupción, exclusividad y enlace/estado del supervisor. Esta observación local no activa envíos automáticos a la web; la consulta desde la interfaz sigue siendo una integración separada.

`export_scan_comparison.py` exporta manualmente una aceptación del observador con sus fuentes y código exactos, tras verificar la custodia. No lee la entrada mutable ni envía datos. El destino debe estar fuera de los runtimes, no se sobrescribe un archivo existente y el paquete web está limitado a 20 MB.

```powershell
python export_scan_comparison.py --scan-runtime private/scan-runtime --runtime private/comparison-runtime --months 2026-09 2026-10 --output private/entregas/comparacion.json
```

La carga de ese paquete en una web privada es un paso manual. La interfaz debe identificar el cálculo como local: conservar bytes y cotejar filas no equivale a recalcular el algoritmo, verificar su bitácora completa o certificar la completitud de los hallazgos. `test_export_scan_comparison.py` verifica originales antes/después, exportación sin envío, rechazo ante alteración y ausencia de sobrescrituras.

## Facturas y cortes comparables

`invoice_adapter.py` extrae la hoja de ítems del XLSX preservando cabeceras, tipos, vacíos y filas. `invoice_core.py` controla claves, números, fechas, cabeceras, posibles recapturas y cambios entre cortes de igual alcance. No se inventan impuestos ni se supone que un documento está completo.

El adaptador rechaza entradas ZIP duplicadas, rutas inseguras, cifrado y compresión no admitida; limita el tamaño comprimido, la expansión y el número de partes. En el XML consumido rechaza DTD, relaciones externas o duplicadas, filas repetidas o desordenadas, coordenadas incompatibles, celdas duplicadas, índices de texto inválidos y números no finitos. Estas comprobaciones protegen la extracción; no autentican al emisor ni prueban la veracidad de una factura.

`invoice_pipeline.py` coteja las celdas del JSON con el XLSX cuando se suministra, conserva originales y referencias y enlaza la ejecución a la bitácora. `invoice_watch.py` selecciona el corte anterior aceptado del mismo universo. Un cambio de política conserva el par de comparación; un universo nuevo inicia otra cadena. Las claves ambiguas se excluyen del cruce.

La política `mindtec-invoice-policy/1` necesita `version`. `line_arithmetic` e `invoice_sum` pueden ser `null`. Una fórmula habilitada requiere evidencia, términos y tolerancia explícitos; la suma documental exige prueba de completitud por documento. Los valores ausentes no se convierten en cero. Una medida no positiva puede corresponder a una bonificación o devolución.

## Linaje hacia los indicadores

`kpi_lineage.py` enlaza dependencias declaradas de líneas de factura y rutas/valores originales de componentes de Perfect Store con hallazgos de sus cortes verificados. Un vínculo identifica un insumo compartido, no un impacto numérico demostrado. La ausencia de vínculos tampoco acredita validación. No une cortes distintos solo porque coincidan IDs ni modifica los valores KPI.

`lineage_bundle.py` produce una proyección compacta de los campos consumidos por el enlace. Omite descripciones y campos ajenos al algoritmo; no reemplaza los originales completos. `verify_lineage_web.py` contrasta la proyección y el evaluador JavaScript con el resultado de archivos completos. La interfaz web y su despliegue privado se mantienen separados de este paquete público.

## Supervisión en Windows

`supervisor.py` permite trabajos `scan`, `invoice`, `lineage`, `feed` y `outbox`, con scripts fijos y rutas absolutas. Rechaza runtimes compartidos, configuraciones de alimentación no enlazadas con el mismo observador Scan y bandejas no enlazadas con sus tres observadores fuente. No ejecuta comandos de shell proporcionados por el JSON.

El supervisor comprueba sus propios handles de proceso. Solo una salida terminal comprobada activa su reinicio con espera creciente. Un estado atrasado o un PID ajeno indican degradación y no autorizan terminar un proceso vivo. Los bloqueos impiden duplicados. Configuración y código operativos quedan archivados por huella.

`windows_job.py` usa un Job Object no heredable para terminar el árbol propio al morir el supervisor. `install-supervisor-task.ps1` permite instalar una tarea oculta del usuario actual, con privilegios limitados, inicio de sesión y comprobación periódica de instancia única. No almacena contraseña y no equivale a un servicio disponible antes del inicio de sesión. Revise los parámetros antes de instalarla.

La señal `stop.request` en el runtime del supervisor impide levantar observadores, incluso durante los disparos periódicos. Para detener permanentemente el arranque, deshabilite la tarea. Los permisos del sistema de archivos siguen siendo necesarios: un administrador con control completo podría reescribir una cadena y sus objetos. Conserve una huella de cierre fuera de ese almacenamiento para verificación independiente.

## Alimentación HTTPS pendiente de acceso autorizado

`scan_feed.py` está preparado para GET HTTPS con límites de tamaño/tiempo, rechazo de redirecciones, contrato estricto y conservación del último corte válido. El ejemplo permanece deshabilitado. El modo `bearer_env` solo es aplicable si el proveedor confirma que es su esquema oficial. No se usan cookies personales ni se guardan credenciales en JSON.

El supervisor rechaza registrar un feed deshabilitado; su runtime, intervalo, entrada y política deben coincidir con la configuración del observador Scan. La validación no lee credenciales ni hace peticiones. No se activa una conexión real ni se crea una cuenta al descargar este código. Consulte [el acceso pendiente](ACCESO_PENDIENTE_SCAN.md) para coordinarlo con el custodio técnico.

Este paquete del motor no incluye el servidor web ni su despliegue, que se mantienen separados. La sincronización autenticada automática de datos con esa web sigue pendiente. La integridad y la concordancia numérica no certifican veracidad documental, representatividad ni probabilidad de fraude.

## Lector ZIP portátil en preparación

`xlsx-zip.mjs` recupera partes internas del XLSX mediante APIs web estándar, sin acceso a archivos, red ni dependencias Node en el módulo. Verifica cabeceras locales y centrales, nombres, descriptores, tamaños, límites de expansión y CRC. Admite ZIP de un solo disco con partes almacenadas o Deflate; rechaza ZIP64, cifrado, enlaces simbólicos, rutas inseguras y codificaciones heredadas no ASCII.

`node --test test-xlsx-zip.mjs` ejecuta sus pruebas sintéticas. `python verify_xlsx_zip_web.py archivo.xlsx --output private/zip-parity.json` compara el SHA-256 de cada parte descomprimida contra el lector independiente de Python. Ese contraste demuestra igualdad de bytes, no validación de los indicadores ni autenticidad del documento.

Referencias del lector: [especificación ZIP de PKWARE](https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT) y [APIs web de Cloudflare Workers](https://developers.cloudflare.com/workers/runtime-apis/web-standards/).

`xlsx-web-core.mjs` interpreta la hoja de ítems de facturas y coteja cabeceras, valores tipados, vacíos, filas originales, nombre de hoja, sistema de fechas y cantidad de fórmulas con el JSON. Conserva el valor almacenado de una fórmula: no la ejecuta ni demuestra que esté actualizado. Los enteros fuera del rango exacto de JavaScript se rechazan. El XML se procesa por bloques con límites de profundidad, elementos y texto, rechazando DTD, entidades no predefinidas, atributos duplicados y estructuras ambiguas.

El analizador SAX se conserva con versión, licencia y hashes en [vendor](vendor/README.md); no requiere instalar paquetes en ejecución. `python -m unittest -v test_xlsx_cells_web` contrasta celdas con el adaptador Python y comprueba rechazos. `node verify-xlsx-cells.mjs original.xlsx corte.json` verifica la huella del XLSX y el cotejo de celdas contra un corte conservado. La integración en el servidor se mantiene en el repositorio privado del Site: conserva el original, resultado y código, y añade una aceptación posterior sin reescribir hallazgos históricos. Las pruebas del módulo no sustituyen la aceptación y verificación de cada archivo en ese servidor.

## Bandeja local para sincronización

`sync_outbox.py` prepara un paquete inmutable de las ejecuciones aceptadas de Scan, facturas y linaje. Exige que los IDs y huellas fuente del linaje correspondan a los cortes seleccionados; si el linaje todavía no aceptó un corte nuevo, conserva el paquete anterior. Requiere los originales de factura ya cotejados. Copia fuentes y referencias desde la custodia verificada, no desde archivos de entrada cambiantes, e incluye políticas, reglas, hallazgos, código y prefijos de bitácora. La proyección para la web se genera desde los cuatro padres conservados por ese linaje, con sus hashes.

El runtime de salida debe estar separado de los tres runtimes fuente. El paquete queda vinculado a un origen HTTPS y al ID explícito del Site. Repetir la preparación con las mismas fuentes, prefijos, destino y código recupera la misma aceptación. Se limita a 100 MB por objeto y 400 MB de evidencia única por paquete. Los prefijos permiten comprobar cadenas de eventos; no incluyen todos los objetos históricos ajenos a las referencias seleccionadas.

```powershell
python sync_outbox.py --invoice-runtime private/invoices-runtime --scan-runtime private/scan-runtime --lineage-runtime private/lineage-runtime --runtime private/sync-runtime --origin https://audit.example.org --project-id appgprj_REPLACE
```

La plantilla de comando requiere sustituir rutas y destino. Preparar no envía datos ni crea una credencial o un recibo remoto: el estado es `prepared_not_sent`. La escritura desatendida y su autorización deben verificarse por separado. Las pruebas de `test_sync_outbox.py` incluyen idempotencia, cortes incompatibles, corrupción, ausencia de originales y aislamiento de la custodia.

`sync_outbox_watch.py` prepara la bandeja continuamente, con intervalo de 30 a 3.600 segundos. Verifica fuentes y salida aun con entradas sin cambios; evita reconstruir y repetir aceptaciones si el token no cambió. Recupera el paquete durable tras reiniciar y conserva la última aceptación al esperar el linaje o encontrar un fallo. El recibo local conserva también el código del observador; no es un recibo de entrega remota.

El trabajo supervisado `kind: outbox` exige `invoice_runtime`, `scan_runtime`, `lineage_runtime`, `runtime`, `origin`, `project_id` e `interval`. Debe enlazarse con exactamente un observador de cada familia y con los mismos runtimes fuente del linaje. Su `health.json` distingue `status: healthy` (preparación local correcta), `state: prepared_not_sent` y `delivery: not_configured`. La pérdida o alteración de la custodia produce degradación, no una confirmación de sincronización. `test_sync_outbox_watch.py` comprueba recuperación, bloqueos, espera coherente y evidencia dañada.

## Cliente de entrega con lectura de confirmación

`sync_client.py` selecciona un paquete verificado de la bandeja cuyo destino coincida con la configuración. Antes de enviar lee y coteja todos los artefactos transferibles. Envía políticas y fuentes a los evaluadores de Scan/facturas, incorpora los originales XLSX y calcula el linaje en el servidor; utiliza los IDs devueltos, sin suponer que coincidan con los IDs locales.

El recibo remoto debe vincular manifiesto, políticas, fuentes, originales y ejecuciones del linaje. El cliente exige la lista exacta de roles comprobados y conserva explícitamente los no comprobados. No acepta afirmaciones de cadena local, padres completos o paridad numérica verificados remotamente. Un POST exitoso no confirma la entrega: debe recuperar por GET el resultado, manifiesto, solicitud y código y comprobar sus huellas y bytes. Solo entonces conserva una aceptación local `delivered_verified` con su evidencia. Al repetir, vuelve a comprobar el recibo remoto y recupera la misma aceptación local.

Copie `sync-client.example.json` en una carpeta privada y sustituya rutas y Site. La plantilla permanece deshabilitada. Use un runtime distinto de la bandeja. La credencial de servicio de Sites se obtiene por un mecanismo autorizado y se inyecta en la variable dedicada indicada por `token_env`; no se guarda en el JSON. `--credential-stdin` admite un pipe oculto de un lanzador autorizado, nunca entrada visible de terminal. Las peticiones HTTPS llevan la credencial solo al origen enlazado; se rechazan redirecciones, respuestas de otro origen, cuerpos excesivos, JSON ambiguo y lecturas con huellas incompatibles.

```powershell
python sync_client.py --config private/sync-client.json
```

Este comando es de una ejecución, no un servicio de envío continuo. La obtención de credenciales sin la sesión de autoría y la programación del emisor requieren configuración separada. Los errores conservan el motivo/estado/etapa y no los cuerpos de error ni las credenciales. Una entrega previa permanece conservada si su comprobación posterior falla. El estado de la bandeja original no se reescribe: sus paquetes siguen siendo evidencia preparada y sus entregas se consultan en el runtime del cliente.

`test_sync_client.py` comprueba ausencia de confirmación ante fallos parciales, recibos incorrectos, custodia alterada, destinos incompatibles y respuestas incompletas, además de idempotencia y exclusividad de la credencial por origen.

## Emisor continuo pendiente de acceso administrado

`sync_delivery_watch.py` entrega paquetes nuevos y vuelve a consultar periódicamente el recibo del paquete sin cambios. Reutiliza la configuración del cliente y obtiene la credencial únicamente de su variable de entorno dedicada. No obtiene credenciales por sí mismo ni descarga la fuente Scan. El suministro y la renovación del acceso deben quedar resueltos antes de instalar una tarea.

```powershell
python sync_delivery_watch.py --config private/sync-client.json --interval 300 --recheck-interval 3600
```

El estado distingue `remote_verified_this_poll` de `local_delivery_custody_verified`. Una comprobación local intermedia conserva la fecha de la última lectura remota; no afirma haber comprobado nuevamente el servidor. Tras reiniciar exige una lectura remota antes de confirmar. Una credencial ausente o un fallo conserva la última aceptación e informa degradación. Los reintentos respetan `Retry-After` y usan espera creciente sin registrar cuerpos ni claves. Un bloqueo exclusivo impide observadores duplicados.

El supervisor admite `kind: publisher`, con `config`, `runtime`, `interval` y `recheck_interval`. Exige un cliente habilitado, runtime separado y exactamente una bandeja configurada con el mismo runtime fuente, origen y proyecto. La validación estructural no consulta credenciales ni acredita que exista acceso. `test_sync_delivery_watch.py` comprueba entregas nuevas, lectura periódica, recuperación, falta de credencial, espera, corrupción y enlace del supervisor.

Esta capacidad está preparada para despliegue. No se activa automáticamente al incorporar el código, y las pruebas sintéticas no demuestran acceso real a Scan ni disponibilidad de una credencial de servicio desatendida.

## Exportaciones normalizadas de colecta

`collection_adapter.py` lee el XLSX de resultados con sus cinco hojas de colecta y conserva coordenadas y tipos originales. `collection_audit.py` audita relaciones, claves ambiguas, conteos, precios y campos de catálogo. Separa meses y aplica exclusiones mediante una correspondencia explícita entre ID interno de Scan e ID Kobo. No confunde un vacío con cero, ni la ausencia en una exportación parcial con una eliminación. Las participaciones calculables se limitan a caras registradas del corte; no certifican los KPI del panel completo.

`collection_watch.py` observa únicamente el archivo seleccionado. Conserva originales, política, correspondencia de IDs, resultado y código en una custodia propia. Recupera la última aceptación tras reiniciar; las entradas incompletas o inválidas quedan rechazadas con evidencia sin sustituirla. Los cambios de política o código se identifican como recálculos, no como cambios de datos. No realiza solicitudes de red ni publicaciones.

```powershell
python collection_watch.py --source private/collection/incoming/current.xlsx --policy private/policy.json --crosswalk private/collection/crosswalk.json --runtime private/collection/runtime --initial-reference private/collection/reference.xlsx --interval 30
```

La referencia inicial es opcional y solo se lee para la primera aceptación. Los cortes siguientes usan originales conservados; un recálculo sin cambios de fuente mantiene la referencia de comparación. La correspondencia debe contener `rows` con pares únicos `internal_id` / `kobo_id`. Las visitas sin correspondencia se conservan, generan una alerta y no entran en cálculos sujetos a exclusiones históricas. Una fórmula con valor en caché no se acepta como observación original.

El supervisor admite `kind: collection`, con `source`, `policy`, `crosswalk`, `runtime`, `interval` (10 a 3.600 segundos) e `initial_reference` opcional; todas las rutas deben ser absolutas y los archivos de entrada deben quedar fuera de la custodia. Su estado distingue `custody_verified` de `network_delivery: false`. Para incorporar una nueva exportación, conserve el original y sustituya atómicamente solo la copia designada; no escriba dentro de `objects` ni edite la bitácora. Este observador no inspecciona Descargas ni sustituye las fuentes de facturas o respuestas crudas de Scan.

Las pruebas `test_collection_audit.py`, `test_collection_watch.py` y `test_collection_supervisor.py` cubren denominadores mensuales, trazabilidad por celda, duplicados, cambios de política, recuperación, rechazo de archivos incompletos, corrupción, exclusión mutua y configuración del supervisor.

## Revisión local con decisiones vinculadas a evidencia

`review_queue.py export` crea una cola JSON fuera de la custodia con hallazgos, revisiones previas, huellas de fuentes y un contrato de decisión para completar. Es una instantánea de lectura; no modifica la bitácora ni supone que una persona haya revisado los datos.

```powershell
python review_queue.py export --runtime private/collection/runtime --output private/revision/cola.json
python report.py --runtime private/collection/runtime --output private/revision/informe.html
```

En el informe de colecta, cada celda citada se coteja con el XLSX conservado: hoja, coordenada, columna, valor e ID interno. No se consulta la copia mutable. Este cotejo prueba correspondencia con el archivo, no veracidad independiente.

Una persona puede copiar `decision_contract` a otro JSON y completar huella del hallazgo, identidad, estado, explicación y referencia de evidencia. Para registrarlo explícitamente:

```powershell
python review_queue.py apply --runtime private/collection/runtime --decision private/revision/decision.json
```

La decisión requiere la ejecución, el insumo y la cabecera exacta de la bitácora exportada. Si otra operación avanzó la bitácora, debe exportarse una cola nueva y reconsiderarse la decisión. Se conserva el archivo de decisión original y se añade un evento; no se reescribe una revisión anterior ni se traslada automáticamente a otros cortes. Los estados admitidos son `en_revision`, `dato_confirmado`, `correccion_solicitada`, `diferencia_explicada` y `sin_evidencia_suficiente`. Una declaración de dato confirmado o diferencia explicada se identifica como decisión registrada; no acredita por sí sola una validación independiente.

La identidad en este flujo local es **declarada**, no autenticada por la plataforma. No sustituye sus permisos ni autoriza sanciones. Las pruebas `test_review_queue.py` incluyen rechazo de decisiones repetidas, desactualizadas, con claves JSON duplicadas, otras fuentes, otras huellas y plantillas sin completar. No se registran revisiones reales a partir de las pruebas sintéticas.

## Cobertura entre exportaciones y métricas sobre pares

Un MAE/RMSE nulo sobre las celdas emparejadas no demuestra igualdad de la cobertura. `collection_impact.py` toma los originales de una ejecución de colecta aceptada, aplica la misma política a ambos lados y describe filas presentes en una sola exportación y diferencias de subtotales conocidos por mes/categoría. No consulta los archivos mutables. Los valores vacíos y las claves ambiguas se cuentan aparte: el subtotal registrado no es un total completo ni un KPI poblacional. Una ausencia no demuestra baja de producto ni fraude.

```powershell
python collection_impact.py --source-runtime private/collection/runtime --runtime private/collection-impact/runtime --output private/revision/impacto.json
python collection_impact_report.py --runtime private/collection-impact/runtime --output private/revision/anexo.html
python review_queue.py export --runtime private/collection-impact/runtime --output private/revision/cola-cobertura.json
```

El anexo mantiene originales, código y señal por fila en una custodia separada. Su informe coteja las celdas citadas con el XLSX de su lado de origen. Los hallazgos de cobertura y los de conteos del corte pueden solaparse; no deben sumarse como errores independientes ni como probabilidad de fraude. Este análisis se ejecuta expresamente por comando: su existencia no acredita que el observador lo regenere ni que se haya publicado en la web.

## Respuestas anchas y reconstrucción operativa de Perfect Store

`flat_answers.py` lee el Excel detallado de Envíos mediante correspondencias exactas entre pregunta, índices de repetición y formulario. Las rutas proceden de un esquema histórico explícito; sus valores históricos no se reutilizan. Las etiquetas ambiguas, celdas en conflicto, rutas sin correspondencia y vacíos quedan identificados. Esta proyección no se presenta como la exportación JSON oficial ni se incorpora automáticamente al observador de respuestas crudas.

`perfect_store.py` calcula los cinco componentes de la reconstrucción documentada: Presencia, SKU núcleo, Frío, POP y Sin quiebre. Requiere configuración explícita de pesos, propietario, canasta de referencias, equivalencias y regla de acceso al frío. El componente SKU usa el proxy histórico de la canasta de precios: no certifica una matriz núcleo oficial. Se distingue la enumeración de todos los enfriadores del formulario anterior de la enumeración BSA del posterior; no se rellena un conteo BSA vacío con el total.

Las repeticiones incompletas y listas sin resolver quedan pendientes; no se convierten automáticamente en cero ni en no aplica. Un puntaje completo requiere resolver todos los componentes aplicables y la elegibilidad. Los límites muestran los extremos por componentes pendientes, no intervalos estadísticos de confianza. El promedio de las fichas completas se etiqueta como parcial. La vista anual incluye solo los meses observados y utiliza observaciones tienda/mes; no representa el año calendario completo.

`perfect_store_check.py` verifica de forma independiente la aritmética de tiendas y agregados, pesos, cobertura y huellas de evidencia. Coteja cada celda con el XLSX conservado. `perfect_store_report.py` genera un HTML autónomo con filtros, estados de componentes, cálculo por tienda y celdas de origen. Indexa las referencias para transporte sin eliminar identificadores; la descarga JSON restaura todas las referencias originales. La serialización descargada no se atribuye a los bytes exactos de la custodia.

```powershell
python perfect_store_report.py --runtime private/perfect-store/runtime --output private/revision/perfect-store.html
```

El evaluador es una biblioteca y el informe opera sobre una ejecución aceptada de tipo `operational_perfect_store`. La preparación de configuración y la admisión de una fuente completa son pasos explícitos; estos módulos no descargan datos, no programan recálculos, no certifican el motor oficial ni cambian el panel automáticamente. Las pruebas de respuestas anchas, Perfect Store, verificación independiente y transporte cubren ambigüedad, ceros/vacíos, repeticiones, aplicabilidad, fórmulas, referencias originales y restauración íntegra de los datos consultables.


`category_eligibility.py` resuelve una rama hija no respondida solo cuando dos listas parentales explícitas y compatibles excluyen su familia y no existe evidencia positiva en sus subcategorías. Los conflictos permanecen documentados. `perfect_store_findings.py` agrupa contradicciones por visita, mes, familia y regla; conserva referencias a respuestas y celdas originales. Sus señales se admiten en una ejecución independiente del motor y pueden exportarse con `review_queue.py`; no deciden fraude, no modifican fuentes y no registran revisiones humanas automáticas. El informe muestra las señales y las exclusiones parentales con su respaldo.


## Observador continuo de Perfect Store

`perfect_store_watch.py` observa una admision local explicita, sin red ni publicacion automatica. La admision `mindtec-perfect-store-admission/1` requiere version, etiqueta y seis fuentes distintas con rutas absolutas y SHA-256: `detailed_workbook`, `normalized_result_workbook`, `historical_question_schema`, `operational_configuration`, `policy_file`, `identity_crosswalk`. Tambien exige `expected_detail_counts`, `expected_normalized_counts` y `expected_eligible_counts`, con conteos positivos y los mismos meses YYYY-MM. Una nueva colecta se admite actualizando este manifiesto deliberadamente cuando sus archivos completos esten descargados; reemplazar un Excel sin actualizar su huella no admite un nuevo corte.

`perfect_store_admission.py` verifica huellas, cobertura declarada, identidades unicas y correspondencia exacta de visita/mes entre ambos archivos tras las exclusiones documentadas. Los renglones de catalogo deben tener padre compatible. No basta que coincidan los conteos. Las preguntas historicas aportan etiquetas/rutas, nunca valores para rellenar el corte nuevo.

```text
python perfect_store_watch.py --admission private/perfect-store/admission.json --runtime private/perfect-store/runtime --report-dir private/perfect-store/reports --interval 60
```

El supervisor admite `kind: perfect_store` con rutas absolutas `admission`, `runtime` y `report_dir`, intervalo minimo30segundos y salidas separadas de toda custodia. Antes de aceptar, el observador valida aritmetica, agregados y todas las celdas citadas, conserva fuentes/configuracion/codigo, registra las contradicciones y genera un HTML inmutable. El informe se retiene tambien como envoltorio JSON/base64 con huella del HTML original. La salud enlaza su ruta y ejecucion. Si falta la copia HTML se restaura desde custodia; una copia alterada se senala sin sobrescribirla. Los candidatos rechazados se conservan, no reemplazan el ultimo resultado aceptado y no acumulan eventos identicos en cada sondeo. Un cambio del codigo exige reiniciar el observador y queda ligado a la nueva ejecucion.

El informe web publicado sigue siendo una instantanea hasta una publicacion manual; el observador solo actualiza resultados locales. La admision explicita no garantiza la veracidad en campo ni certifica la formula oficial, y las senales requieren revision humana. El registro de salud no prueba que un proceso siga vivo: se contrasta con su proceso propietario al verificar la instalacion.


## Distribucion numerica desde presencia declarada

`numeric_distribution.py` deriva el indicador de presencia del ultimo Perfect Store aceptado: tiendas con marca / tiendas que venden categoria. Exige la cohorte y el catalogo completos; conserva todas las combinaciones marca/categoria/mes, incluso sin base elegible. Una ausencia explicita produce cero; una respuesta pendiente no. Publica un porcentaje exacto solo con elegibilidad y presencia resueltas, y en otro caso limites aritmeticos de datos faltantes, no intervalos de confianza. El ano observado utiliza suma de numeradores y denominadores de tienda/mes, no promedio de porcentajes mensuales.

`numeric_distribution_run.py` lee la ultima admision aceptada por el observador PS dentro de una transaccion verificada, coteja originales y alcance, y conserva ejecucion fuente, respuestas originales, configuracion, politica, admision y codigo en una custodia separada. No adopta una ejecucion PS meramente calculada que aun no tenga evento de aceptacion. `numeric_distribution_report.py` crea un HTML autonomo con filtros, grafico del porcentaje o sus limites, visitas elegibles/no elegibles y celdas. Esta derivacion se ejecuta por comando; no es un octavo observador instalado ni certifica coincidencia con el panel oficial.

```text
python numeric_distribution_run.py --ps-runtime private/perfect-store/runtime --runtime private/numeric-distribution/runtime
python numeric_distribution_report.py --runtime private/numeric-distribution/runtime --output private/revision/distribucion-numerica.html
```

Las pruebas enumeran asignaciones posibles de datos faltantes para comprobar limites, distinguen base cero de porcentaje cero y prueban el agrupamiento anual con denominadores desiguales. La derivacion comparte la presencia del PS operativo, por lo que no se presenta como una segunda observacion independiente del campo.

Los resultados de distribucion conservan tambien las senales de categoria de cada visita y su regla/motivo de elegibilidad. Un porcentaje aritmeticamente completo no suprime una contradiccion de fuente ni equivale a una revision humana favorable.


## Share de estante con denominador verificable

`shelf_share.py` vuelve a leer las caras de la colecta original y usa la elegibilidad de categoria de la ejecucion PS aceptada. Exige que coincidan cantidad esperada de marcas, seleccion, identidades y repeticiones; rechaza conteos vacios/ambiguos, negativos, fraccionarios, booleanos o textuales como medidas confirmadas. No mezcla caras frias ni promedia porcentajes por tienda. Las ramas otras marcas y sus columnas sin vinculo se conservan para revision: no suma padre e hijos por suposicion. La vinculacion de columnas usa nombres de categoria exactos, no prefijos que mezclen categorias similares.

Si falta cualquier visita aplicable, el share de toda la base queda pendiente. Se mantienen las caras conocidas de marca/categoria como subtotales, sin presentarlas como totales ni sustituir vacios por cero. Sin tiendas elegibles, cero caras observadas y un share real de cero son estados diferentes. El ano observado agrupa sumas de caras y conserva el alcance de los meses disponibles. Las incidencias se agrupan por visita y categoria, sin multiplicarlas por marca ni decidir fraude.

```text
python shelf_share_run.py --provenance-runtime private/numeric-distribution/runtime --runtime private/shelf-share/runtime
python shelf_share_report.py --runtime private/shelf-share/runtime --output private/revision/share-estante.html
```

El ejecutor utiliza la procedencia PS aceptada y conservada en la custodia de distribucion; no usa los porcentajes de distribucion como entrada numerica. Conserva originales, admision, politica, fuente PS, su implementacion y el codigo del nuevo calculo. El informe incluye filtros, graficos de resultados completos, detalle por visita e incidencias con celdas; no se publica un porcentaje completo para subtotales. Son comandos locales, no otro observador instalado ni sincronizacion con el sitio. La equivalencia con el panel oficial requiere cortes y reglas compatibles.


### Estructuras verificadas de otras marcas

`other_faces.py` aplica una configuracion `mindtec-other-face-layouts/1` ligada al SHA-256 del XLSX detallado y al nombre exacto del formulario. Sin configuracion mantiene la rama pendiente. Se admiten dos estructuras: conteo agregado en la fila principal, o suma de hijas cuya primera fila coincide con indice del padre y ordinal1 y cuyas filas posteriores tienen rutas completas explicitas. Exige numero de hijas, ordinales, nombre de producto y caras validos. Un padre con caras simultaneas en la estructura anidada, filas adicionales, alias contradictorios o celdas no vinculadas impiden aceptar el total. Nunca agrega padre e hijos juntos ni convierte el nombre/SKU escrito en una marca maestra.

```text
python shelf_share_run.py --provenance-runtime private/numeric-distribution/runtime --runtime private/shelf-share/runtime --other-rules private/other-layout-rules.json
```

La configuracion exige observaciones por formulario con rutas absolutas y SHA-256, conservadas como envoltorios base64 con huella del original. Cambiar el archivo fuente o la evidencia sin nueva admision rechaza el calculo. Las referencias reconstruidas indican si el vinculo proviene de ruta completa o de la regla admitida de primera hija. Es una interpretacion tecnica documentada del formato, no una certificacion oficial ni una revision humana favorable sobre la encuesta.


### Actividad ambigua fuera de la enumeracion de marcas

El lector generico conserva repeticiones candidatas cuando una celda compartida tiene texto. El calculo de estante distingue esa incertidumbre de evidencia de una fila fisica adicional: solo separa el nombre generico ambiguo fuera del rango declarado cuando numero esperado y seleccion unica coinciden, todos sus valores no vacios proceden exclusivamente del encabezado compartido «Cual es el nombre de esta otra marca», y no hay valor propio en alias explicitos, codigos, caras, SKU u otro campo. Si el nombre esta dentro de las filas esperadas o existe cualquier evidencia especifica de fila (incluso0caras), mantiene el bloqueo. Comprueba tambien indices de repeticion completos.

La celda y sus rutas candidatas quedan conservadas sin asignarlas a ninguna marca/categoria. Se registran observaciones informativas agrupadas por celda original; no se multiplican por categoria ni se presentan como revisiones humanas favorables. Se distinguen de los bloqueos que impiden un denominador. El informe muestra ambas clases y senala los resultados completos que conservan incertidumbre de texto auxiliar.


### Vista conjunta de reconstrucciones compatibles

`integrated_reconstruction.py` exige una ejecucion PS aceptada por el observador, la misma huella de respuestas y politica, identidades de tienda/marca/categoria coincidentes y referencias de celdas verificables. Distribucion y estante deben declarar exactamente la ejecucion y snapshot PS comunes. Conserva los resultados fuente en custodia separada y crea una proyeccion de campos seleccionados con indices y huellas de origen; no sustituye los resultados originales completos.

```text
python integrated_reconstruction.py --ps-runtime private/perfect-store-continuous/runtime --distribution-runtime private/numeric-distribution/runtime --shelf-runtime private/shelf-share/runtime --runtime private/integrated-reconstruction/runtime
python integrated_report.py --runtime private/integrated-reconstruction/runtime --output private/revision/reconstrucciones.html
```

El HTML usa filtros compartidos de periodo, marca, categoria y empresa historica. Conserva marcas sin homologacion y visitas no elegibles. Muestra PS, distribucion y estante por separado, sus pendientes, componentes, pesos, denominadores, celdas y hallazgos de origen. La vista anual retiene la agregacion de cada indicador: media de puntajes PS, distribucion por visitas/mes y estante por suma de caras. Los otros nueve KPI muestran requisitos especificos; no se imputan con datos de otro indicador. La empresa historica no acredita relacion con un distribuidor.

`integrated_transport.py` compacta referencias mediante indices reversibles. La descarga restaura exactamente la proyeccion retenida y los IDs de evidencia originales, sin atribuirle identidad de bytes con todos los archivos fuente. La configuracion operativa y las exclusiones permanecen visibles. No calcula una confianza global ni prueba veracidad de campo, causalidad o fraude. El HTML es de lectura; no guarda decisiones humanas. Son ejecuciones por comando e instantaneas de publicacion manual, no un observador adicional ni envios automaticos. El codigo y fixtures sinteticos pueden compartirse; los informes, fuentes y configuraciones reales conservan su acceso privado.


### Share en frio con universos explicitos

`cold_share.py` deriva caras frias por categoria desde respuestas originales, sin usar caras de estante ni cifras publicadas. Exige enumeracion completa, codigos unicos y conteos enteros no negativos. La lista global del formulario anterior conserva evidencia pero no se reparte entre categorias por el nombre de marca. No convierte un campo vacio en cero, ni un subtotal conocido en denominador completo. El ano observado suma caras y permanece pendiente si falta algun mes aplicable.

```text
python cold_share_run.py --provenance-runtime private/numeric-distribution/runtime --runtime private/cold-share/runtime --cooler-rules private/cold-share/cooler-scope-rules.json
python cold_share_report.py --runtime private/cold-share/runtime --output private/revision/share-frio.html
```

`--cooler-rules` es opcional. Sin regla admitida se mantiene la interpretacion conservadora. La configuracion `mindtec-cold-layout/1` vincula SHA del XLSX, version, formulario exacto y observaciones externas por ruta y huella. Solo admite `explicit_zero_bsa_count_means_no_bsa_cold_faces`: cero equipos especificamente pertenecientes a bebidas sin alcohol o que las contienen permite cero caras BSA, con puerta positiva de equipos y sin filas o conteos contradictorios. No se extiende a lacteos ni utiliza un total general para completar el conteo BSA. Cada formulario configurado exige evidencia conservada en un envoltorio con su huella original; alterar la evidencia rechaza el calculo.

Si aparecen filas frias en una categoria excluida, se conserva la decision de origen y el conflicto queda pendiente en este indicador, sin eliminar la visita del denominador por conveniencia. Las limitaciones de esquema son informativas y distintas de contradicciones o datos vacios; ninguna senal determina fraude. Se conservan originales, fuente PS aceptada, politica, admision, configuracion observada y codigo en custodia propia. La vista HTML tiene filtros de marca/categoria/mes/ano, grafico solo para puntos completos, visitas y celdas, con descarga que restaura exactamente el resultado retenido. El transporte agrupa listas de referencias repetidas sin cambiar IDs ni valores.

Son comandos locales e instantaneas; todavia no constituyen otro observador continuo ni una actualizacion del sitio hospedado. Los conteos de caras no acreditan temperatura, funcionamiento o acceso comercial a equipos. La equivalencia con el panel requiere version, universo y reglas compatibles. Los insumos, evidencias UI y resultados reales permanecen privados; solo codigo y fixtures sinteticos se comparten.


### Integrar frio en la vista compartida

La integracion admite opcionalmente una cuarta custodia con `--cold-runtime`. Comprueba la misma fuente PS, snapshot, XLSX y politica; el catalogo, cohorte, inventarios y referencias de agregados deben ser exhaustivos. La decision de elegibilidad original se conserva aun cuando el indicador de frio deba abrir un conflicto adicional. Nunca sobreescribe los valores ni denominadores de PS, distribucion o estante. La union de evidencia preserva las huellas originales y rechaza conflictos o referencias ausentes.

```text
python integrated_reconstruction.py --ps-runtime private/perfect-store-continuous/runtime --distribution-runtime private/numeric-distribution/runtime --shelf-runtime private/shelf-share/runtime --cold-runtime private/cold-share/runtime --runtime private/integrated-four/runtime
python integrated_report.py --runtime private/integrated-four/runtime --output private/revision/cuatro-indicadores.html
```

El mismo renderizador admite tres o cuatro indicadores. Agrega columna, filtros, grafico, visitas y celdas de frio y conserva las limitaciones de esquema como una clase distinta de los nombres auxiliares informativos. La lista global antigua deja pendientes los resultados por categoria, incluido el ano observado; no se omite un mes para completar el total. Las fuentes, configuracion de alcance observada, ejecuciones y codigo retenido de frio quedan vinculados a la proyeccion. Los ocho KPI restantes conservan sus requisitos especificos. Esta integracion es una instantanea de publicacion manual, no instala otro observador ni activa envios.


### Disponibilidad declarada y alcance del cuestionario

`declared_availability.py` calcula ausencia de quiebre declarado por empresa entre tiendas que dicen comprar a esa empresa; su complemento es el quiebre declarado. No mide inventario fisico de SKU ni disponibilidad independiente de cada marca. Las referencias de marca conservan la homologacion historica y comparten el mismo resultado empresarial, sin multiplicar la muestra. Se conservan las marcas sin homologacion.

La configuracion opcional `mindtec-company-question-universe/1` vincula archivo de respuestas, version, formulario exacto, empresas ofrecidas y observaciones conservadas por huella. Una empresa no ofrecida queda sin medicion. Sin universo admitido, una empresa no seleccionada permanece desconocida. La ausencia solo acredita no comprador cuando la empresa era una opcion y la seleccion, contador e identidades de las repeticiones son completos. Se diferencian no comprador, no preguntado, pendiente, quiebre y ausencia de quiebre. El ano suma tiendas/mes, sin omitir meses no cubiertos para completar un punto.

```text
python declared_availability_run.py --provenance-runtime private/numeric-distribution/runtime --runtime private/availability/runtime --question-universe private/availability/question-universe.json --definition-evidence private/availability/definition.txt --definition-sha256 SHA256_DE_LA_EVIDENCIA
python declared_availability_report.py --runtime private/availability/runtime --output private/revision/sin-quiebre.html
```

El ejecutor conserva fuentes PS aceptadas, originales, politica, admision, codigo y observaciones; rechaza huellas alteradas. El informe presenta empresas, referencias de marca, visitas y celdas, y descarga el resultado retenido. No instala otro observador ni activa envios. Las senales no deciden fraude ni validan automaticamente respuestas.

### Perfect Store: no preguntado no equivale a No aplica

PS operativo2.2.0 exige universo de empresas ofrecidas y enumeracion completa para declarar No aplica por ausencia de compra. Una empresa fuera de las opciones del formulario, o sin universo admitido, deja el componente Sin quiebre pendiente. Una declaracion negativa con detalles de agotamiento contradictorios tambien queda pendiente. Una respuesta explicita de la empresa compradora sigue siendo una declaracion empresarial, no inventario de SKU.

`stock_question_universe` en la configuracion PS usa el mismo contrato y observaciones originales retenidas como base64 con su huella; deben cubrir cada formulario admitido y coincidir con el SHA del XLSX. Cambiar esta configuracion requiere una nueva admision. El observador conserva versiones previas y admite el recalculo con su codigo/configuracion nuevos. Las demas componentes y elegibilidades no se corrigen por suposicion. El modulo de disponibilidad puede detectar el uso historico de No aplica para empresas no ofrecidas, como hallazgo metodologico trazable, sin inventar un puntaje corregido ni inferir revisiones humanas.

### Referencia empresarial en la vista conjunta

`integrated_reconstruction.py --availability-runtime` incorpora opcionalmente la reconstruccion empresarial a la misma custodia de PS/distribucion/estante/frio. Rechaza politica, XLSX, ejecucion PS, snapshot, visitas, catalogo o empresa historica incompatibles. Comprueba la totalidad de las visitas por empresa, la identidad y unicidad de sus referencias y los agregados mensuales/anuales contra todas sus declaraciones. Conserva definicion, universos de pregunta, observaciones y codigo fuente con sus huellas. El resultado empresarial no se recalcula a partir de porcentajes publicados.

```powershell
python integrated_reconstruction.py --ps-runtime private/perfect-store-continuous/runtime --distribution-runtime private/numeric-distribution/runtime --shelf-runtime private/shelf-share/runtime --cold-runtime private/cold-share/runtime --availability-runtime private/availability/runtime --runtime private/integrated-five/runtime
python integrated_report.py --runtime private/integrated-five/runtime --output private/revision/indicadores-y-referencia-empresarial.html
```

La seccion empresarial usa una fila por empresa/periodo, sin multiplicar la muestra por marca o categoria. Los filtros de marca/categoria eligen referencias historicas; no reducen el denominador empresarial. Mantiene visitas no compradoras, empresas no ofrecidas y observaciones pendientes como estados distintos. La vista anual suma compradores de los meses observados y no publica un punto omitiendo meses sin cobertura. Cada fila abre todas las visitas y sus celdas originales. El JSON descargado restaura exactamente la proyeccion retenida, incluida esta evidencia. La regla oficial de disponibilidad de marca/SKU sigue siendo un requisito separado; esta referencia no la certifica. No se instala otro observador ni se habilitan descargas o envios automaticos.
