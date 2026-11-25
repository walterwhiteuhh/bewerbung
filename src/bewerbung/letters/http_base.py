"""Gemeinsame HTTP-Logik für Anbieter ohne eigenes SDK (OpenAI, Gemini).

Bewusst über ``httpx`` statt über die Hersteller-SDKs: ein Aufruf pro Anschreiben braucht
keine weiteren Abhängigkeiten, und die Fehlerbehandlung bleibt an einer Stelle.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from bewerbung.letters.base import GenerationError

logger = logging.getLogger(__name__)


def post_json(
    client: httpx.Client | None,
    *,
    label: str,
    url: str,
    headers: dict[str, str],
    payload: dict[str, Any],
    timeout: float,
) -> dict[str, Any]:
    """POST mit einheitlichen deutschen Fehlermeldungen; der Key taucht nie im Log auf."""
    try:
        if client is not None:
            resp = client.post(url, headers=headers, json=payload, timeout=timeout)
        else:
            with httpx.Client(timeout=timeout) as c:
                resp = c.post(url, headers=headers, json=payload)
    except httpx.TimeoutException as exc:
        raise GenerationError(f"{label} hat nicht rechtzeitig geantwortet") from exc
    except httpx.HTTPError as exc:
        raise GenerationError(f"{label} nicht erreichbar") from exc

    if resp.status_code in (401, 403):
        raise GenerationError("API-Key ungültig oder ohne Berechtigung")
    if resp.status_code == 429:
        raise GenerationError("Zu viele Anfragen oder Guthaben aufgebraucht")
    if resp.status_code >= 400:
        logger.warning("%s Fehler %s: %s", label, resp.status_code, resp.text[:500])
        raise GenerationError(f"{label} Fehler {resp.status_code}")
    try:
        data = resp.json()
    except ValueError as exc:
        raise GenerationError(f"{label} lieferte keine gültige Antwort") from exc
    if not isinstance(data, dict):
        raise GenerationError(f"{label} lieferte keine gültige Antwort")
    return data
