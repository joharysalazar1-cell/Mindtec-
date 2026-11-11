# MindTEC · Dashboard privado con control continuo

El dashboard original del 11/11/2026 se conserva en `source/baseline.html.gz`. El build comprueba y registra su SHA-256; extrae sin modificar los estilos, el HTML de la interfaz, los datos y el JavaScript histórico. Únicamente cambia el arranque para recuperar la base por versión y añade el botón «Control continuo · versiones y auditoría».

## Ejecución y verificación

Requiere Node 24 o posterior. El Worker no necesita dependencias npm ni ejecuta Python.

```
node build-audit.cjs
node test-audit.mjs
node dev-audit.mjs
```

La vista local está restringida a 127.0.0.1:4173, usa una identidad simulada y una base SQLite efímera. Nunca se importa ese servidor en producción. La publicación usa `dist/server/index.js`, Cloudflare D1 (`DB`) y R2 (`BUCKET`), y las migraciones de `drizzle/`.

## Qué queda registrado

- La base histórica lleva manifiesto, hash exacto del JSON incorporado, hash del HTML original y commit de referencia del repositorio Mindtec-.
- Cada nuevo corte conserva un archivo JSON gzip independiente en R2 y una ficha en D1: actor autenticado, fecha, motivo, versión padre y SHA-256 del gzip exacto. Las fichas no sobrescriben versiones anteriores.
- Las revisiones registran resultado o clave trazable, versión, estado, explicación y referencia de evidencia. Un cambio de estado se representa como otra revisión; no se edita el evento anterior.
- D1 guarda una cadena SHA-256. El evento y la ficha se insertan en un batch transaccional; una restricción única en la huella anterior evita bifurcaciones concurrentes. Las huellas pueden exportarse y verificarse en el navegador.
- El comparador de versiones contrasta facturas por Clave trazable y exporta diferencias, altas y bajas completas. No trata facturas como ventas.

## Límites explícitos

La estructura de una carga se comprueba en el navegador para procesar bases grandes sin exceder la memoria del Worker. El servidor verifica el SHA-256 del archivo comprimido y guarda el resumen como declaración del actor; no certifica su exactitud. Admite JSON completo de este dashboard, máximo 60 MB sin comprimir y 12 MB comprimidos. No ingiere Excel o CSV sin normalización.

El acceso privado lo exige Sites; las operaciones de historial requieren además la identidad autenticada recibida del servidor. Las escrituras comprueban origen y tipo de contenido. No hay credenciales en el cliente, el código o el manifiesto.

La cadena detecta modificaciones internas, pero no sustituye un archivo externo de huellas ni impide que un administrador reescriba todo el almacenamiento. Exportar y conservar las huellas fuera del sistema permite controles independientes.

Las notas locales de las pantallas históricas siguen siendo locales, tal como indican sus textos originales. Para revisiones persistentes debe utilizarse Control continuo. Los controles de confianza históricos y D01–D08 se conservan; «Documentado» no significa validación integral.

No existe una conexión API real configurada ni ejecución programada. Las bases se incorporan manualmente. Para automatizar será necesario definir endpoint autorizado, esquema, periodicidad y reglas de conciliación. El motor Python del repositorio se mantiene como referencia independiente; no se presenta como ejecutado en esta web.

Los datos reales y los archivos originales deben permanecer fuera del repositorio público de GitHub. El repositorio privado del alojamiento conserva la base de esta publicación. No se fusionó ni reemplazó el motor Streamlit de main.
