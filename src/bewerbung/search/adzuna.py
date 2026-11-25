"""Adzuna-Such-API (bündelt Anzeigen vieler Portale). Braucht kostenlose App-ID und Key.

Doku: https://developer.adzuna.com/docs/search
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from bewerbung.domain.enums import JobSource
from bewerbung.search.base import ListingDraft, ProviderError, SearchQuery

logger = logging.getLogger(__name__)

BASE_URL = "https://api.adzuna.com/v1/api/jobs/de/search/1"
_CONTRACT = {"full_time": "Vollzeit", "part_time": "Teilzeit"}


def to_draft(item: dict[str, Any]) -> ListingDraft | None:
    if not item.get("id") or not item.get("title"):
        return None
    created = item.get("created")
    posted = None
    if isinstance(created, str):
        try:
            posted = datetime.fromisoformat(created.replace("Z", "+00:00")).astimezone(UTC)
        except ValueError:
            posted = None
    predicted = str(item.get("salary_is_predicted", "0")) == "1"
    return ListingDraft(
        source=JobSource.ADZUNA,
        external_id=str(item["id"]),
        url=item.get("redirect_url"),
        title=str(item["title"]).strip(),
        company_name=(item.get("company") or {}).get("display_name"),
        location=(item.get("location") or {}).get("display_name"),
        employment_type=_CONTRACT.get(str(item.get("contract_time"))),
        # Von Adzuna geschätzte Gehälter nicht als Angabe übernehmen (bleiben in raw).
        salary_min=None if predicted else _int(item.get("salary_min")),
        salary_max=None if predicted else _int(item.get("salary_max")),
        salary_currency=None if predicted or item.get("salary_min") is None else "EUR",
        description=item.get("description"),
        posted_at=posted,
        raw=item,
    )


def _int(value: Any) -> int | None:
    try:
        return round(float(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


class AdzunaProvider:
    source = JobSource.ADZUNA
    label = "Adzuna"

    def __init__(
        self,
        app_id: str | None,
        app_key: str | None,
        timeout: float = 15.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._transport = transport
        self._app_id = app_id
        self._app_key = app_key
        self._timeout = timeout

    @property
    def unavailable_reason(self) -> str | None:
        if not (self._app_id and self._app_key):
            return "API-Key fehlt (BEWERBUNG_ADZUNA_APP_ID / _APP_KEY in .env)"
        return None

    async def search(self, query: SearchQuery) -> list[ListingDraft]:
        if self.unavailable_reason:
            raise ProviderError(self.unavailable_reason)
        what = f"{query.query} remote" if query.remote_only else query.query
        params: dict[str, str | int] = {
            "app_id": self._app_id or "",
            "app_key": self._app_key or "",
            "what": what,
            "results_per_page": query.limit,
            "content-type": "application/json",
        }
        if query.location:
            params["where"] = query.location
            if query.radius_km is not None:
                params["distance"] = query.radius_km
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                resp = await client.get(BASE_URL, params=params)
        except httpx.HTTPError as exc:
            raise ProviderError(f"Adzuna nicht erreichbar: {exc}") from exc
        if resp.status_code != 200:
            raise ProviderError(f"Adzuna antwortet mit {resp.status_code}")
        drafts = [d for d in (to_draft(i) for i in resp.json().get("results", [])) if d]
        logger.info("Adzuna: %d Treffer für %r", len(drafts), query.query)
        return drafts
