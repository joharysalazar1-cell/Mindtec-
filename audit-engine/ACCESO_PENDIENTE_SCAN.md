# Acceso pendiente para alimentación continua de Scan

El motor local, la custodia y la supervisión funcionan. La descarga desatendida aún no está autorizada/configurada. La API de exportación comprobada devuelve HTTP 401 fuera de la sesión del navegador. No se reutilizaron cookies personales, no se crearon credenciales y no se cambiaron permisos.

Sistemas debe confirmar:

1. Endpoint oficial de exportación de solo lectura y su contrato/versionado: cuestionarios normalizados, campos, universo y paginación si existe.
2. Método oficial de autenticación para un proceso desatendido y alcance mínimo de lectura. El soporte Bearer del conector es una capacidad preparada, no una afirmación sobre la API actual.
3. Cómo se administra e inyecta la credencial sin compartirla por chat ni guardarla en archivos de datos; caducidad, rotación y revocación.
4. Frecuencia y límites permitidos, tratamiento de HTTP 429, ETag/304 si están disponibles y metadatos que identifiquen el corte exportado.
5. Entorno de operación: equipo con sesión de usuario o servicio gestionado, custodio técnico y forma de comunicar incidencias de alimentación.

Después se debe probar una descarga autorizada, contrastar sus bytes/total/universo con una exportación oficial, conservar esa aceptación y verificar recuperación tras un fallo sin sustituirla. Solo entonces se habilitará el conector y se incorporará al supervisor. La configuración preparada permanece deshabilitada.

Este documento es un pedido técnico para revisión local; no fue enviado a ninguna persona ni servicio.
