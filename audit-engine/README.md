# Motor continuo de auditor�a MindTEC

Motor de lectura y control de calidad de datos con fuentes inmutables, reglas versionadas, bit�cora verificable y revisi�n humana. Una se�al no demuestra fraude ni provoca correcciones o sanciones autom�ticas. No se punt�an personas ni se infiere duraci�n de una encuesta a partir de su fecha de env�o.

## Requisitos y comprobaciones

Python 3.10 o posterior y biblioteca est�ndar. Los contrastes JavaScript requieren Node.js. La protecci�n nativa de procesos y la instalaci�n de tareas se prueban en Windows; sus pruebas se omiten en otros sistemas.

```powershell
cd audit-engine
python -m unittest -v
```

Las pruebas usan datos sint�ticos. Los datos reales, informes, XLSX, im�genes, configuraciones activas, credenciales y bases de ejecuci�n se mantienen fuera del repositorio. Las plantillas JSON no contienen exclusiones reales ni secretos.

## Colecta Scan

Prepare una exportaci�n completa con `envios`, `total` y respuestas `ruta`/`valor`, m�s una pol�tica derivada de `policy.example.json`. Las exclusiones necesitan ID, motivo y evidencia.

```powershell
python engine.py run --runtime private/scan-runtime --source private/scan.json --policy private/policy.json
python engine.py watch --runtime private/scan-runtime --source private/scan.json --policy private/policy.json --interval 10
python engine.py verify --runtime private/scan-runtime
python report.py --runtime private/scan-runtime --output private/informe.html
```

Controles: claves duplicadas, respuestas incompatibles, contradicciones de categor�a, conteos inv�lidos, GPS fuera de dominio e identificador de tienda ausente. Las marcas enumeradas en fr�o con cero caras se tratan como informaci�n que requiere interpretar la definici�n del formulario; no se convierten en presencia positiva ni en acusaciones.

## Facturas y cortes comparables

`invoice_adapter.py` extrae la hoja de �tems del XLSX preservando cabeceras, tipos, vac�os y filas. `invoice_core.py` controla claves, n�meros, fechas, cabeceras, posibles recapturas y cambios entre cortes de igual alcance. No se inventan impuestos ni se supone que un documento est� completo.

El adaptador rechaza entradas ZIP duplicadas, rutas inseguras, cifrado y compresi�n no admitida; limita el tama�o comprimido, la expansi�n y el n�mero de partes. En el XML consumido rechaza DTD, relaciones externas o duplicadas, filas repetidas o desordenadas, coordenadas incompatibles, celdas duplicadas, �ndices de texto inv�lidos y n�meros no finitos. Estas comprobaciones protegen la extracci�n; no autentican al emisor ni prueban la veracidad de una factura.

`invoice_pipeline.py` coteja las celdas del JSON con el XLSX cuando se suministra, conserva originales y referencias y enlaza la ejecuci�n a la bit�cora. `invoice_watch.py` selecciona el corte anterior aceptado del mismo universo. Un cambio de pol�tica conserva el par de comparaci�n; un universo nuevo inicia otra cadena. Las claves ambiguas se excluyen del cruce.

La pol�tica `mindtec-invoice-policy/1` necesita `version`. `line_arithmetic` e `invoice_sum` pueden ser `null`. Una f�rmula habilitada requiere evidencia, t�rminos y tolerancia expl�citos; la suma documental exige prueba de completitud por documento. Los valores ausentes no se convierten en cero. Una medida no positiva puede corresponder a una bonificaci�n o devoluci�n.

## Linaje hacia los indicadores

`kpi_lineage.py` enlaza dependencias declaradas de l�neas de factura y rutas/valores originales de componentes de Perfect Store con hallazgos de sus cortes verificados. Un v�nculo identifica un insumo compartido, no un impacto num�rico demostrado. La ausencia de v�nculos tampoco acredita validaci�n. No une cortes distintos solo porque coincidan IDs ni modifica los valores KPI.

`lineage_bundle.py` produce una proyecci�n compacta de los campos consumidos por el enlace. Omite descripciones y campos ajenos al algoritmo; no reemplaza los originales completos. `verify_lineage_web.py` contrasta la proyecci�n y el evaluador JavaScript con el resultado de archivos completos. La interfaz web y su despliegue privado se mantienen separados de este paquete p�blico.

## Supervisi�n en Windows

`supervisor.py` permite trabajos `scan`, `invoice`, `lineage` y `feed`, con scripts fijos y rutas absolutas. Rechaza runtimes compartidos y configuraciones de alimentaci�n no enlazadas con el mismo observador Scan. No ejecuta comandos de shell proporcionados por el JSON.

El supervisor comprueba sus propios handles de proceso. Solo una salida terminal comprobada activa su reinicio con espera creciente. Un estado atrasado o un PID ajeno indican degradaci�n y no autorizan terminar un proceso vivo. Los bloqueos impiden duplicados. Configuraci�n y c�digo operativos quedan archivados por huella.

`windows_job.py` usa un Job Object no heredable para terminar el �rbol propio al morir el supervisor. `install-supervisor-task.ps1` permite instalar una tarea oculta del usuario actual, con privilegios limitados, inicio de sesi�n y comprobaci�n peri�dica de instancia �nica. No almacena contrase�a y no equivale a un servicio disponible antes del inicio de sesi�n. Revise los par�metros antes de instalarla.

La se�al `stop.request` en el runtime del supervisor impide levantar observadores, incluso durante los disparos peri�dicos. Para detener permanentemente el arranque, deshabilite la tarea. Los permisos del sistema de archivos siguen siendo necesarios: un administrador con control completo podr�a reescribir una cadena y sus objetos. Conserve una huella de cierre fuera de ese almacenamiento para verificaci�n independiente.

## Alimentaci�n HTTPS pendiente de acceso autorizado

`scan_feed.py` est� preparado para GET HTTPS con l�mites de tama�o/tiempo, rechazo de redirecciones, contrato estricto y conservaci�n del �ltimo corte v�lido. El ejemplo permanece deshabilitado. El modo `bearer_env` solo es aplicable si el proveedor confirma que es su esquema oficial. No se usan cookies personales ni se guardan credenciales en JSON.

El supervisor rechaza registrar un feed deshabilitado; su runtime, intervalo, entrada y pol�tica deben coincidir con la configuraci�n del observador Scan. La validaci�n no lee credenciales ni hace peticiones. No se activa una conexi�n real ni se crea una cuenta al descargar este c�digo. Consulte [el acceso pendiente](ACCESO_PENDIENTE_SCAN.md) para coordinarlo con el custodio t�cnico.

Este paquete no incluye sincronizaci�n autenticada autom�tica con una web ni cotejo XLSX dentro de esa web. La integridad y la concordancia num�rica no certifican veracidad documental, representatividad ni probabilidad de fraude.
