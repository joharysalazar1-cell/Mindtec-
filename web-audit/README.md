# Dashboard privado MindTEC

Esta capa web conserva el dashboard original y añade versiones y revisiones persistentes. El motor Python existente conserva su ejecución independiente.

Los datos reales se excluyen del repositorio público. Para construir, suministra localmente `source/baseline.html.gz` con el HTML completo del dashboard del 11/11/2026. Configura `.openai/hosting.json` con el ID real de tu Site privado y los bindings `d1: "DB"` y `r2: "BUCKET"` antes del build. No publiques el HTML, el gzip, los manifiestos con datos ni `dist/` en GitHub.

Node 24+: `node build-audit.cjs`, `node test-audit.mjs`. Consulta [las condiciones de auditoría](README-AUDITORIA.md). Las pruebas de preservación necesitan la base privada de referencia; las pruebas no contienen datos de clientes.

La actualización actual es por carga JSON controlada. La conexión automática a fuentes y el recalculo mediante el motor Python requieren una integración posterior explícita.
