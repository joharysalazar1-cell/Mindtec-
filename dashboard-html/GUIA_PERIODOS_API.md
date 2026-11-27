# Perfect Store: periodos extensibles y API (rama de revisión)

## Alcance

El generador `reconstruct_perfect_store.py` ahora selecciona **los meses realmente presentes** en el JSON de visitas normalizadas. No presupone dos meses ni 108 visitas. La misma tienda puede participar en varios meses; una segunda observación en el mismo mes requiere revisión/exclusión explícita. Solo se excluyen los envíos definidos en la conciliación aprobada. La cantidad de registros incluidos y su distribución mensual se guardan en el manifiesto, junto con el hash SHA-256 del JSON normalizado.

**Esto NO convierte el dashboard HTML en una API en vivo.** El HTML sigue siendo un corte estático; cada cambio de datos requiere reconstruir el JSON, el informe y el HTML. Tampoco reemplaza las reglas históricas de Perfect Store, el catálogo Scan, los cubos ni las capturas oficiales.

## Prueba sintética (desde raíz del repositorio)

```powershell
python -m unittest discover -s dashboard-html -p "test_period_utils.py" -v
python -m unittest discover -s dashboard-html -p "test_api_questionnaires.py" -v
node dashboard-html/test-source.cjs
```

Las pruebas funcionales del dashboard actual necesitan el corte privado local y tienen expectativas históricas de septiembre/octubre. No utilizar estas pruebas para certificar datos de noviembre.

## Archivos normalizados (API o JSON privado)

La API HTTPS **debe responder con un JSON completo normalizado**, no un CSV o export crudo de KoBo. Formato mínimo:

```json
{
  "generado": "2026-11-23T12:00:00Z",
  "envios": [
    {
      "envioKobo": "demo_001",
      "fechaVisita": "2026-11-15",
      "codigoTienda": "DEMO_T01",
      "respuestas": [
        {"ruta": "pregunta_demo", "pregunta": "Pregunta demo", "valor": "si"}
      ]
    }
  ]
}
```

Las respuestas reales del formulario utilizan rutas específicas, incluyendo repeticiones de productos, enfriadores y marcas. El ejemplo prueba estructura, **no es suficiente para calcular Perfect Store oficial**. Las rutas y homologaciones deben verificarse antes del uso empresarial.

### API key segura (solo sesión de PowerShell)

```powershell
$env:MINDTEC_QUESTIONNAIRES_API_URL = "https://servidor-autorizado.ejemplo/api/export"
$env:MINDTEC_QUESTIONNAIRES_API_KEY = "<clave-configurada-localmente>"
# Opcional si la API exige X-API-Key:
# $env:MINDTEC_QUESTIONNAIRES_API_HEADER = "X-API-Key"
# $env:MINDTEC_QUESTIONNAIRES_API_PREFIX = ""
```

La URL anterior es **ilustrativa, no un endpoint real**. Nunca pegues la clave en GitHub, logs, capturas, prompts de un modelo externo o mensajes. Configura las variables en tu sesión segura o un gestor de secretos aprobado.

El lector exige HTTPS, no sigue redirecciones, limita la respuesta a 25 MB, y rechaza los formatos no normalizados y ciertas señales de paginación. Si la API real tiene `data.items`, paginación, OAuth, límites u otros esquemas, adapta el conector a su contrato **antes de utilizar datos reales**. Para objeto anidado puedes configurar `MINDTEC_QUESTIONNAIRES_RECORDS_PATH`, pero aun así debes garantizar que la extracción sea completa.

### Reconstrucción desde API autorizada

```powershell
python dashboard-html/reconstruct_perfect_store.py `
  --api `
  --start-month 2026-09 `
  --end-month 2026-11 `
  --cut-id 2026-11-23 `
  --data-dir "C:\ruta\privada\auditoria" `
  --downloads-dir "C:\ruta\privada\exportaciones"
```

Además del JSON de cuestionarios, el reconstructor sigue necesitando los insumos auxiliares: Excel de Scan, configuración de clientes/SKU, conciliación y exclusiones aprobadas, HTML histórico y cubos comparables de cada mes. Los valores predeterminados apuntan a archivos históricos del proyecto. Para otros cortes utiliza `--scan-xlsx`, `--config-json`, `--exclusions-json`, `--historical-html`, `--published-capture` según corresponda; las rutas deben ser archivos privados locales. Los cubos siguen siendo `cubo_embol_YYYY-MM.csv` dentro de `--downloads-dir`. La ausencia de cubos se indica en el manifiesto, no se interpreta como un cero comercial.

Para verificar cobertura, añade `--expected-visits N` **solo si el número esperado está confirmado por una fuente externa**. El script falla si hay discrepancia, sin asumir 54 tiendas por mes.

### Reconstruir informe y adjuntar al HTML

```powershell
python dashboard-html/build_perfect_store_report.py --data-dir "C:\ruta\privada\auditoria" --cut-id 2026-11-23
python dashboard-html/build.py --data-dir "C:\ruta\privada\auditoria" --perfect-store-cut 2026-11-23
```

El último comando continúa exigiendo los tres insumos históricos del dashboard ejecutivo documentados en `README.md`; **no convierte automáticamente los otros 11 KPI en datos dinámicos**.

## Seguridad, reproducibilidad y límites

- Repositorio **público**: nunca subir envíos, fichas, facturas, JSON privados, credenciales ni HTML/ZIP con registros incrustados.
- Cada corte se guarda en `Perfect_Store_reconstruido_YYYY-MM-DD`. Para evitar reemplazar resultados previos, el script falla si el corte ya tiene manifiesto. `--overwrite-cut` exige una decisión explícita.
- El nombre del corte no reemplaza la fecha real de colecta. El manifiesto conserva los meses y el hash del contenido importado.
- Las reglas de SKU núcleo, frío, POP y quiebres siguen siendo una **reconstrucción operativa**; no certifican la configuración histórica del servidor.
- El comparador oficial puede no estar disponible para meses nuevos; en ese caso debe quedar sin par y no inventarse un 0 o una coincidencia.
- Los nombres de algunas fuentes, capturas y reglas provienen del piloto de 2026; revisar la compatibilidad de los insumos antes de declarar un corte posterior como válido.
- La app Streamlit tiene otro conector (`src/services/auto_sources.py`), que acepta CSV/JSON generales; este reconstructor necesita específicamente JSON normalizado con `envios`.
- La rama y la PR requieren ejecutar pruebas locales y revisión antes de integrarse en `main`.
