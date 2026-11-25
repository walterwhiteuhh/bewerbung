"""Remotive-API: Remote-Stellen weltweit, kostenlos und ohne Key.

Nur Anzeigen, die aus Deutschland/Europa besetzt werden dürfen, werden übernommen.
Remotive bittet um sparsame Nutzung (wenige Abrufe pro Tag); die App fragt nur bei
einer Suche an.
"""

from __future__ import annotations

import logging
import re
from typing import Any

import httpx

from bewerbung.domain.enums import JobSource, RemoteType
from bewerbung.search.base import ListingDraft, ProviderError, SearchQuery
from bewerbung.search.common import clean_html, matches_all, parse_datetime, query_terms

logger = logging.getLogger(__name__)

BASE_URL = "https://remotive.com/api/remote-jobs"
_TYPES = {
    "full_time": "Vollzeit",
    "part_time": "Teilzeit",
    "contract": "Freiberuflich/Projekt",
    "freelance": "Freiberuflich/Projekt",
    "internship": "Praktikum",
}
_ALLOWED_REGION = re.compile(
    r"germany|deutschland|dach|europe|europa|\beu\b|emea|worldwide|anywhere|global|cet|gmt",
    re.IGNORECASE,
)
_WORK_TIME_TYPES = {"vollzeit": {"full_time"}, "teilzeit": {"part_time"}, "minijob": {"part_time"}}


def to_draft(item: dict[str, Any]) -> ListingDraft | None:
    if not item.get("id") or not item.get("title"):
        return None
    region = str(item.get("candidate_required_location") or "").strip()
    return ListingDraft(
        source=JobSource.REMOTIVE,
        external_id=str(item["id"]),
        url=item.get("url"),
        title=str(item["title"]).strip(),
        company_name=item.get("company_name"),
        location=f"Remote ({region})" if region else "Remote",
        remote_type=RemoteType.REMOTE,
        employment_type=_TYPES.get(str(item.get("job_type"))),
        description=clean_html(item.get("description")),
        posted_at=parse_datetime(item.get("publication_date")),
        raw=item,
    )


class RemotiveProvider:
    source = JobSource.REMOTIVE
    label = "Remotive (remote)"

    def __init__(
        self, timeout: float = 15.0, transport: httpx.AsyncBaseTransport | None = None
    ) -> None:
        self._timeout = timeout
        self._transport = transport

    @property
    def unavailable_reason(self) -> str | None:
        return None

    async def search(self, query: SearchQuery) -> list[ListingDraft]:
        # Reine Remote-Börse: bei Ausbildung oder Schicht-/Minijob-Suchen nichts Sinnvolles.
        if query.offer_type in {"ausbildung", "selbststaendig"} or "schicht" in query.work_times:
            return []
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                resp = await client.get(
                    BASE_URL, params={"search": query.query, "limit": max(query.limit * 2, 50)}
                )
        except httpx.HTTPError as exc:
            raise ProviderError("Remotive nicht erreichbar") from exc
        if resp.status_code != 200:
            raise ProviderError(f"Remotive antwortet mit {resp.status_code}")
        try:
            jobs = resp.json().get("jobs") or []
        except ValueError as exc:
            raise ProviderError("Remotive liefert kein JSON") from exc
        allowed_types = set().union(*(_WORK_TIME_TYPES.get(w, set()) for w in query.work_times))
        if query.offer_type == "praktikum":
            allowed_types = {"internship"}
        # Remotive ignoriert "search" teilweise (liefert beliebige Stellen): lokal nachfiltern.
        terms = query_terms(query.query)
        drafts = []
        for job in jobs:
            if not matches_all(terms, job.get("title"), job.get("tags"), job.get("description")):
                continue
            region = str(job.get("candidate_required_location") or "")
            if region and not _ALLOWED_REGION.search(region):
                continue
            if allowed_types and job.get("job_type") not in allowed_types:
                continue
            if draft := to_draft(job):
                drafts.append(draft)
        logger.info(
            "Remotive: %d passende von %d Treffern für %r", len(drafts), len(jobs), query.query
        )
        return drafts[: query.limit]
