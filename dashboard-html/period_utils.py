"""Period selection for MindTEC questionnaire exports (no implicit exclusions)."""
from collections import Counter
from datetime import date
import re

MONTH_PATTERN = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def valid_month(value):
    if value is None:
        return None
    if not isinstance(value, str) or not MONTH_PATTERN.fullmatch(value):
        raise ValueError("El periodo debe usar el formato YYYY-MM (ej.: 2026-11).")
    return value


def select_visits(envios, excluded_ids=(), start_month=None, end_month=None):
    """Select included visits and discover observed months, without guessing sample size.

    A store may occur in multiple months but not twice in the same month.
    Duplicate store-month submissions require explicit review/exclusion.
    """
    start = valid_month(start_month)
    end = valid_month(end_month)
    if start and end and start > end:
        raise ValueError("--start-month debe ser anterior o igual a --end-month.")
    if not isinstance(envios, list):
        raise ValueError("El origen normalizado debe contener una lista 'envios'.")

    excluded = {str(x).strip() for x in excluded_ids}
    selected, seen = [], set()
    for index, record in enumerate(envios):
        if not isinstance(record, dict):
            raise ValueError(f"Envío #{index + 1} no es un objeto.")
        raw_date = str(record.get("fechaVisita") or "")
        try:
            day = date.fromisoformat(raw_date[:10])
        except ValueError:
            raise ValueError(f"Envío #{index + 1}: fechaVisita debe ser una fecha ISO válida.") from None
        month = day.strftime("%Y-%m")
        if (start and month < start) or (end and month > end):
            continue
        envio = str(record.get("envioKobo") or "").strip()
        if not envio:
            raise ValueError(f"Envío #{index + 1}: falta envioKobo.")
        if envio in excluded:
            continue
        sticker = str(record.get("codigoTienda") or "").strip()
        if not sticker:
            raise ValueError(f"Envío {envio}: falta codigoTienda.")
        if not isinstance(record.get("respuestas"), list):
            raise ValueError(f"Envío {envio}: falta la lista normalizada de respuestas.")
        key = (month, sticker)
        if key in seen:
            raise ValueError(
                f"Tienda repetida dentro del mes {month}: {sticker}. "
                "Revisar envíos y exclusiones antes de reconstruir."
            )
        seen.add(key)
        selected.append(record)

    if not selected:
        raise ValueError("No hay visitas válidas para el rango de meses solicitado.")
    return selected, sorted(Counter(str(r["fechaVisita"])[:7] for r in selected))
