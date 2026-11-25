"""Jooble-API: Aggregator, der sehr viele Jobbörsen und Karriereseiten bündelt.

Kostenloser Key über https://jooble.org/api/about. Eine Anfrage = ein POST mit JSON.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

import httpx

from bewerbung.domain.enums import JobSource
from bewerbung.search.base import ListingDraft, ProviderError, SearchQuery
from bewerbung.search.common import clean_html, parse_datetime

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "https://jooble.org/api/"
_TYPES = {"full-time": "Vollzeit", "part-time": "Teilzeit", "temporary": "Befristet"}


def to_draft(item: dict[str, Any]) -> ListingDraft | None:
    title, link = item.get("title"), item.get("link")
    if not title or not link:
        return None
    # Jooble liefert eine numerische ID; ohne sie den Link hashen, damit Dubletten erkannt werden.
    ext = str(item.get("id") or hashlib.sha256(str(link).encode()).hexdigest()[:24])
    job_type = str(item.get("type") or "").strip()
    return ListingDraft(
        source=JobSource.JOOBLE,
        external_id=ext,
        url=str(link),
        title=clean_html(title) or str(title),
        company_name=(item.get("company") or None),
        location=(item.get("location") or None),
        employment_type=_TYPES.get(job_type.casefold(), job_type or None),
        description=clean_html(item.get("snippet")),
        posted_at=parse_datetime(item.get("updated")),
        raw=item,
    )


class JoobleProvider:
    source = JobSource.JOOBLE
    label = "Jooble"

    def __init__(
        self,
        api_key: str | None,
        timeout: float = 15.0,
        base_url: str = DEFAULT_BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._timeout = timeout
        self._base_url = base_url.rstrip("/") + "/"
        self._transport = transport

    @property
    def unavailable_reason(self) -> str | None:
        if not self._api_key:
            return "API-Key fehlt (BEWERBUNG_JOOBLE_API_KEY in .env)"
        return None

    async def search(self, query: SearchQuery) -> list[ListingDraft]:
        if reason := self.unavailable_reason:
            raise ProviderError(reason)
        words = [query.query]
        if query.remote_only:
            words.append("homeoffice")
        if query.work_times == ["minijob"]:
            words.append("minijob")
        elif query.work_times == ["teilzeit"]:
            words.append("teilzeit")
        if query.offer_type in {"ausbildung", "praktikum"}:
            words.append(query.offer_type)
        body: dict[str, str] = {
            "keywords": " ".join(words),
            "location": query.location or "Deutschland",
            "page": "1",
            "ResultOnPage": str(query.limit),
        }
        if query.location and query.radius_km:
            body["radius"] = str(query.radius_km)
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                resp = await client.post(f"{self._base_url}{self._api_key}", json=body)
        except httpx.HTTPError as exc:
            raise ProviderError("Jooble nicht erreichbar") from exc
        if resp.status_code in (401, 403):
            raise ProviderError("Jooble: API-Key ungültig")
        if resp.status_code != 200:
            raise ProviderError(f"Jooble antwortet mit {resp.status_code}")
        try:
            jobs = resp.json().get("jobs") or []
        except ValueError as exc:
            raise ProviderError("Jooble liefert kein JSON") from exc
        drafts = [d for d in (to_draft(j) for j in jobs) if d is not None]
        logger.info("Jooble: %d Treffer für %r", len(drafts), query.query)
        return drafts[: query.limit]
