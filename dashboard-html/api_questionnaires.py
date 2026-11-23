"""Opt-in, read-only HTTPS import of normalized questionnaire exports.

Environment variables:
  MINDTEC_QUESTIONNAIRES_API_URL: full HTTPS export endpoint, without credentials
  MINDTEC_QUESTIONNAIRES_API_KEY: secret
  MINDTEC_QUESTIONNAIRES_API_HEADER: Authorization (default) or X-API-Key
  MINDTEC_QUESTIONNAIRES_API_PREFIX: Bearer  (default) or empty for X-API-Key
  MINDTEC_QUESTIONNAIRES_RECORDS_PATH: optional dotted path to normalized data

No URL redirections. No logs of secrets or API response bodies.
"""
import json
import os
from urllib.parse import urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch_normalized_export(max_bytes=25 * 1024 * 1024):
    url = os.environ.get("MINDTEC_QUESTIONNAIRES_API_URL", "")
    key = os.environ.get("MINDTEC_QUESTIONNAIRES_API_KEY", "")
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment:
        raise ValueError("Configura MINDTEC_QUESTIONNAIRES_API_URL con HTTPS y sin credenciales en la URL.")
    if not key:
        raise ValueError("Falta MINDTEC_QUESTIONNAIRES_API_KEY.")
    header = os.environ.get("MINDTEC_QUESTIONNAIRES_API_HEADER", "Authorization")
    prefix = os.environ.get("MINDTEC_QUESTIONNAIRES_API_PREFIX", "Bearer ")
    if header.lower() not in ("authorization", "x-api-key"):
        raise ValueError("Encabezado permitido: Authorization o X-API-Key.")
    request = Request(
        url,
        headers={"Accept": "application/json", header: prefix + key},
        method="GET",
    )
    try:
        with build_opener(NoRedirect()).open(request, timeout=30) as response:
            body = response.read(max_bytes + 1)
    except Exception as exc:
        # Do not print exception details: URLs may contain sensitive query arguments.
        raise RuntimeError(f"Error de consulta API: {type(exc).__name__}.") from None
    if len(body) > max_bytes:
        raise ValueError("Respuesta superior a 25 MB: utiliza un endpoint acotado o paginado con un adaptador.")

    try:
        payload = json.loads(body)
        route = os.environ.get("MINDTEC_QUESTIONNAIRES_RECORDS_PATH", "")
        for part in route.split(".") if route else []:
            payload = payload[part]
    except (ValueError, KeyError, TypeError, IndexError):
        raise ValueError("La respuesta no contiene el JSON normalizado en la ruta indicada.") from None

    if not isinstance(payload, dict) or not isinstance(payload.get("envios"), list):
        raise ValueError("La API debe devolver {envios:[...]}; CSV y KoBo crudo necesitan otro adaptador.")
    if payload.get("next") or payload.get("next_page") or payload.get("has_more") is True:
        raise ValueError("Export paginado: el adaptador debe recuperar todas las páginas antes de auditar.")
    return payload
