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

`supervisor.py` permite trabajos `scan`, `invoice`, `lineage` y `feed`, con scripts fijos y rutas absolutas. Rechaza runtimes compartidos y configuraciones de alimentación no enlazadas con el mismo observador Scan. No ejecuta comandos de shell proporcionados por el JSON.

El supervisor comprueba sus propios handles de proceso. Solo una salida terminal comprobada activa su reinicio con espera creciente. Un estado atrasado o un PID ajeno indican degradación y no autorizan terminar un proceso vivo. Los bloqueos impiden duplicados. Configuración y código operativos quedan archivados por huella.

`windows_job.py` usa un Job Object no heredable para terminar el árbol propio al morir el supervisor. `install-supervisor-task.ps1` permite instalar una tarea oculta del usuario actual, con privilegios limitados, inicio de sesión y comprobación periódica de instancia única. No almacena contraseña y no equivale a un servicio disponible antes del inicio de sesión. Revise los parámetros antes de instalarla.

La señal `stop.request` en el runtime del supervisor impide levantar observadores, incluso durante los disparos periódicos. Para detener permanentemente el arranque, deshabilite la tarea. Los permisos del sistema de archivos siguen siendo necesarios: un administrador con control completo podría reescribir una cadena y sus objetos. Conserve una huella de cierre fuera de ese almacenamiento para verificación independiente.

## Alimentación HTTPS pendiente de acceso autorizado

`scan_feed.py` está preparado para GET HTTPS con límites de tamaño/tiempo, rechazo de redirecciones, contrato estricto y conservación del último corte válido. El ejemplo permanece deshabilitado. El modo `bearer_env` solo es aplicable si el proveedor confirma que es su esquema oficial. No se usan cookies personales ni se guardan credenciales en JSON.

El supervisor rechaza registrar un feed deshabilitado; su runtime, intervalo, entrada y política deben coincidir con la configuración del observador Scan. La validación no lee credenciales ni hace peticiones. No se activa una conexión real ni se crea una cuenta al descargar este código. Consulte [el acceso pendiente](ACCESO_PENDIENTE_SCAN.md) para coordinarlo con el custodio técnico.

Este paquete no incluye sincronización autenticada automática con una web ni cotejo XLSX dentro de esa web. La integridad y la concordancia numérica no certifican veracidad documental, representatividad ni probabilidad de fraude.
