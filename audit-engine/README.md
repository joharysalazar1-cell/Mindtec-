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

```powershell
python engine.py run --runtime private/scan-runtime --source private/scan.json --policy private/policy.json
python engine.py watch --runtime private/scan-runtime --source private/scan.json --policy private/policy.json --interval 10
python engine.py verify --runtime private/scan-runtime
python report.py --runtime private/scan-runtime --output private/informe.html
```

Controles: claves duplicadas, respuestas incompatibles, contradicciones de categoría, conteos inválidos, GPS fuera de dominio e identificador de tienda ausente. Las marcas enumeradas en frío con cero caras se tratan como información que requiere interpretar la definición del formulario; no se convierten en presencia positiva ni en acusaciones.

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
