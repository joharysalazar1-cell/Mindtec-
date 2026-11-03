# Motor de auditoría y fuentes automáticas

## Ejecutar y explorar

Desde la carpeta que contiene app.py:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Se incluyen dos fuentes DEMO sintéticas sin información de clientes. En Indicadores verificables selecciona observaciones, modo Tiendas, identificador tienda, elegibilidad elegible = 1 y condición marca = Demo: el resultado es 3/4 = 75%. En Contraste de fuentes selecciona ambos archivos demo, clave tienda y medida caras_marca, documenta el mismo periodo y alcance: verás coincidencias, una diferencia y tiendas presentes solo en una fuente.

Auditoría de la base identifica faltantes y duplicados. Indicadores calcula ratios explícitos; Contraste cruza claves únicas sin multiplicar filas. Resultados conserva evidencia y resolución en memoria y permite descargar CSV/JSON. El auditor avanzado mantiene su carga propia de CSV. Modelos incluye OLS multivariable y logística binaria exploratoria con interacción opcional.

## API sin subir archivos manualmente

Define en el entorno del proceso que ejecuta Streamlit:

- MINDTEC_API_URL: endpoint HTTPS de exportación.
- MINDTEC_API_KEY: secreto. Nunca guardarlo en Git ni compartirlo por una captura.
- MINDTEC_API_FORMAT: json (predeterminado) o csv.
- MINDTEC_API_RECORDS_PATH: ruta hacia la lista JSON, por ejemplo data.items; vacío si la respuesta es la lista.
- MINDTEC_API_HEADER: Authorization por defecto.
- MINDTEC_API_PREFIX: Bearer seguido de espacio por defecto; para X-API-Key usar prefijo vacío.

Para múltiples endpoints copia config/sources.example.json como config/sources.local.json, que se excluye de Git, y configura una entrada por fuente. Las claves se resuelven desde variables de entorno, no desde JSON. No se siguen redirecciones con la credencial. Peticiones GET, timeout de 20 segundos, máximo 25 MB; respuestas CSV UTF-8 o JSON de objetos.

La conexión se intenta al abrir la aplicación. Se comprueban vencimientos cada 60 segundos mientras la sesión está abierta; el intervalo por fuente es 300 segundos por defecto (mínimo 60). La página Fuentes automáticas permite forzar consulta. Los fallos conservan el último snapshot y muestran un estado; los snapshots anteriores se conservan en la sesión. No hay sincronización cuando la aplicación no está ejecutándose. La API debe proporcionar el export completo: paginación u OAuth requieren adaptar el conector al contrato real.

La extracción no se ha conectado a un servicio real: faltan endpoint, API key y ejemplo de respuesta. No se adivinan rutas del dashboard ni se utilizan cookies del navegador.

## Compartir

GitHub aloja el código. Otra persona puede clonarlo y ejecutar los comandos anteriores para explorar la demo. Para una URL compartida con ejecución en navegador hay que desplegar Streamlit en un servicio o servidor, configurando allí las credenciales. No publicar una instancia con fuentes de clientes sin definir sus usuarios y acceso.

## Verificación

```powershell
python -m unittest discover -s tests -v
```

Las pruebas cubren claves ambiguas, cruce externo, tolerancias, división por cero, ratios, flujo de interfaz, lectura API y conservación de fuentes ante fallos. No certifican equivalencia con el dashboard: eso exige fuentes del mismo corte y fórmulas comparables.

## Carga manual y archivo local

La opción **Cargar bases de datos** admite varios CSV, XLSX o XLS. Selecciona el tipo de fuente, periodo, procedencia y unidad de observación. La revisión de columnas muestra compatibilidad estructural y campos pendientes; no certifica que los valores sean correctos. También permite inspeccionar fechas frente a un corte.

Con **Guardar original y periodo en historial local** se conserva el archivo original por hash y una ficha de versión en data/staging/uploads, excluido de Git. Puedes recuperarlo desde esa misma pantalla tras reiniciar la sesión. Los archivos con el mismo nombre y distinto contenido se distinguen por hash. El historial vive en el equipo o volumen del servidor; GitHub no transporta estas bases ni sustituye una copia de respaldo.
