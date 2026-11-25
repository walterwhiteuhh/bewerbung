"""Jobsuche-API der Bundesagentur für Arbeit (öffentlich, fester Client-Schlüssel).

Doku: https://jobsuche.api.bund.dev/

Seit Ende 2026 liefert nur noch ``/pc/v6/jobs`` Daten (v4 antwortet mit 403).
v6 hat andere Feldnamen; das Mapping liest zusätzlich die alten v4-Namen, damit
ältere Rohdaten in ``listings.raw_payload`` weiterhin verständlich bleiben.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from bewerbung.domain.enums import JobSource, RemoteType
from bewerbung.search.base import ListingDraft, ProviderError, SearchQuery

logger = logging.getLogger(__name__)

BASE_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v6/jobs"
DETAIL_URL = "https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"


def _parse_date(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _first_str(item: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _company(item: dict[str, Any]) -> str | None:
    firma = item.get("firma")
    if isinstance(firma, dict):
        firma = firma.get("name")
    if isinstance(firma, str) and firma.strip():
        return firma.strip()
    return _first_str(item, "arbeitgeber")


def _location(item: dict[str, Any]) -> str | None:
    place: dict[str, Any] = {}
    lokationen = item.get("stellenlokationen")
    if isinstance(lokationen, list) and lokationen and isinstance(lokationen[0], dict):
        place = lokationen[0].get("adresse") or lokationen[0]
    elif isinstance(item.get("arbeitsort"), dict):  # v4
        place = item["arbeitsort"]
    parts = [p for p in (place.get("ort"), place.get("region")) if isinstance(p, str) and p]
    return ", ".join(parts) or None


def to_draft(item: dict[str, Any]) -> ListingDraft | None:
    refnr = _first_str(item, "referenznummer", "refnr")
    title = _first_str(item, "stellenangebotsTitel", "titel", "beruf")
    if not refnr or not title:
        return None
    return ListingDraft(
        source=JobSource.ARBEITSAGENTUR,
        external_id=refnr.lower(),
        url=_first_str(item, "externeURL", "externeUrl") or DETAIL_URL.format(refnr=refnr),
        title=title,
        company_name=_company(item),
        location=_location(item),
        posted_at=_parse_date(
            item.get("datumErsteVeroeffentlichung") or item.get("aktuelleVeroeffentlichungsdatum")
        ),
        raw=item,
    )


class ArbeitsagenturProvider:
    source = JobSource.ARBEITSAGENTUR
    label = "Arbeitsagentur"

    def __init__(
        self,
        api_key: str,
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._transport = transport
        self._api_key = api_key
        self._timeout = timeout

    @property
    def unavailable_reason(self) -> str | None:
        return None

    async def search(self, query: SearchQuery) -> list[ListingDraft]:
        params: dict[str, str | int] = {
            "was": query.query,
            "size": query.limit,
            "page": 1,
            "angebotsart": 1,  # Arbeit (keine Ausbildung/Selbstständigkeit)
        }
        if query.location:
            params["wo"] = query.location
            if query.radius_km is not None:
                params["umkreis"] = query.radius_km
        if query.remote_only:
            # v6: nur Anzeigen mit Homeoffice-Anteil (> 0 %), nicht zwingend voll remote.
            params["homeoffice"] = "prozentual_0"
        headers = {"X-API-Key": self._api_key, "User-Agent": "Bewerbungsmanager/0.3"}
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                resp = await client.get(BASE_URL, params=params, headers=headers)
        except httpx.HTTPError as exc:
            raise ProviderError(f"Arbeitsagentur nicht erreichbar: {exc}") from exc
        if resp.status_code != 200:
            raise ProviderError(f"Arbeitsagentur antwortet mit {resp.status_code}")
        try:
            payload = resp.json()
        except ValueError as exc:
            raise ProviderError("Arbeitsagentur liefert kein JSON") from exc
        # "ergebnisliste" fehlt bei 0 Treffern.
        items = payload.get("ergebnisliste") or payload.get("stellenangebote") or []
        drafts = [d for d in (to_draft(i) for i in items) if d is not None]
        if query.remote_only:
            drafts = [d.model_copy(update={"remote_type": RemoteType.HYBRID}) for d in drafts]
        logger.info("Arbeitsagentur: %d Treffer für %r", len(drafts), query.query)
        return drafts
