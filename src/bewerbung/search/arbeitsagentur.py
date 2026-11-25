"""Jobsuche-API der Bundesagentur für Arbeit (öffentlich, fester Client-Schlüssel).

Doku: https://jobsuche.api.bund.dev/
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from bewerbung.domain.enums import JobSource, RemoteType
from bewerbung.search.base import ListingDraft, ProviderError, SearchQuery

logger = logging.getLogger(__name__)

BASE_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
DETAIL_URL = "https://www.arbeitsagentur.de/jobsuche/jobdetail/{refnr}"


def _parse_date(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def to_draft(item: dict[str, Any]) -> ListingDraft | None:
    refnr = item.get("refnr")
    title = item.get("titel") or item.get("beruf")
    if not refnr or not title:
        return None
    place = item.get("arbeitsort") or {}
    location = ", ".join(p for p in (place.get("ort"), place.get("region")) if p) or None
    return ListingDraft(
        source=JobSource.ARBEITSAGENTUR,
        external_id=str(refnr).lower(),
        url=item.get("externeUrl") or DETAIL_URL.format(refnr=refnr),
        title=str(title).strip(),
        company_name=item.get("arbeitgeber"),
        location=location,
        posted_at=_parse_date(item.get("aktuelleVeroeffentlichungsdatum")),
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
            params["arbeitszeit"] = "ho"  # Homeoffice
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
        items = resp.json().get("stellenangebote") or []
        drafts = [d for d in (to_draft(i) for i in items) if d is not None]
        if query.remote_only:
            drafts = [d.model_copy(update={"remote_type": RemoteType.REMOTE}) for d in drafts]
        logger.info("Arbeitsagentur: %d Treffer für %r", len(drafts), query.query)
        return drafts
