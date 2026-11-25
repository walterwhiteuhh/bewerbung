"""Arbeitnow Job-Board-API: kostenlos, ohne Key, Schwerpunkt Deutschland/Europa.

Die API hat keine Suchparameter, sondern liefert die neuesten Anzeigen seitenweise.
Deshalb werden einige Seiten geladen und lokal nach Begriffen, Ort und Filtern gefiltert.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import httpx

from bewerbung.domain.enums import WORK_TIME_LABEL, JobSource, RemoteType
from bewerbung.domain.logos import logo_from_payload
from bewerbung.search.base import ListingDraft, ProviderError, SearchQuery
from bewerbung.search.common import clean_html, matches_all, parse_datetime, query_terms

logger = logging.getLogger(__name__)

BASE_URL = "https://www.arbeitnow.com/api/job-board-api"
PAGES = 3
_TYPE_WORDS = {
    "vollzeit": ("full time", "full-time", "vollzeit"),
    "teilzeit": ("part time", "part-time", "teilzeit"),
    "minijob": ("mini", "minijob", "450", "520", "538", "556", "geringfügig"),
    "schicht": ("shift", "schicht", "nacht", "wochenende"),
}


def to_draft(item: dict[str, Any]) -> ListingDraft | None:
    if not item.get("slug") or not item.get("title"):
        return None
    job_types = [str(t) for t in item.get("job_types") or []]
    return ListingDraft(
        source=JobSource.ARBEITNOW,
        external_id=str(item["slug"]),
        url=item.get("url"),
        title=str(item["title"]).strip(),
        company_name=item.get("company_name"),
        company_logo_url=logo_from_payload(item),
        location=item.get("location"),
        remote_type=RemoteType.REMOTE if item.get("remote") else RemoteType.UNKNOWN,
        employment_type=", ".join(job_types) or None,
        description=clean_html(item.get("description")),
        posted_at=parse_datetime(item.get("created_at")),
        raw=item,
    )


def _place_ok(item: dict[str, Any], query: SearchQuery) -> bool:
    if query.remote_only and not item.get("remote"):
        return False
    if query.location and not item.get("remote"):
        return query.location.casefold().strip() in str(item.get("location") or "").casefold()
    return True


def _kind_ok(item: dict[str, Any], query: SearchQuery) -> bool:
    title = str(item.get("title") or "").casefold()
    types = " ".join(map(str, item.get("job_types") or [])).casefold()
    if query.work_times and not any(
        w in types or w in title for wt in query.work_times for w in _TYPE_WORDS[wt]
    ):
        return False
    if query.offer_type == "ausbildung":
        return "ausbildung" in title
    if query.offer_type == "praktikum":
        return "praktik" in f"{title} {types}" or "intern" in f"{title} {types}"
    return True


def _wanted(item: dict[str, Any], query: SearchQuery, terms: list[str]) -> bool:
    return (
        matches_all(terms, item.get("title"), item.get("tags"), item.get("description"))
        and _place_ok(item, query)
        and _kind_ok(item, query)
    )


class ArbeitnowProvider:
    source = JobSource.ARBEITNOW
    label = "Arbeitnow"

    def __init__(
        self, timeout: float = 15.0, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._timeout = timeout
        self._transport = transport

    @property
    def unavailable_reason(self) -> str | None:
        return None

    async def search(self, query: SearchQuery) -> list[ListingDraft]:
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                transport=self._transport,
                headers={"User-Agent": "Bewerbungsmanager/0.4"},
            ) as client:
                responses = await asyncio.gather(
                    *(client.get(BASE_URL, params={"page": p}) for p in range(1, PAGES + 1)),
                    return_exceptions=True,
                )
        except httpx.HTTPError as exc:
            raise ProviderError("Arbeitnow nicht erreichbar") from exc
        items: list[dict[str, Any]] = []
        for resp in responses:
            if isinstance(resp, BaseException) or resp.status_code != 200:
                continue
            try:
                items.extend(resp.json().get("data") or [])
            except ValueError:
                continue
        if not items:
            raise ProviderError("Arbeitnow liefert gerade keine Daten")
        terms = query_terms(query.query)
        drafts = [
            d for d in (to_draft(i) for i in items if _wanted(i, query, terms)) if d is not None
        ]
        if len(query.work_times) == 1:
            label = WORK_TIME_LABEL[query.work_times[0]]
            drafts = [
                d if d.employment_type else d.model_copy(update={"employment_type": label})
                for d in drafts
            ]
        logger.info(
            "Arbeitnow: %d von %d Anzeigen passen zu %r", len(drafts), len(items), query.query
        )
        return drafts[: query.limit]
