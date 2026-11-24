"""Schnittstelle für Quellen (LinkedIn, Stepstone, ...).

Iteration 1 nutzt nur ``identify``: aus einer eingefügten URL werden Quelle,
externe ID und eine normalisierte URL abgeleitet (Dublettenschutz).
``fetch`` ist der Andockpunkt für spätere Live-Importer (API oder Scraper).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from urllib.parse import SplitResult, parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict, Field

from bewerbung.domain.enums import JobSource, RemoteType

_TRACKING_PREFIXES = ("utm_", "trk", "ref", "src", "cmp", "gclid", "fbclid", "mc_")


class SourceReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: JobSource
    external_id: str | None = None
    url_normalized: str


class JobPostingDraft(BaseModel):
    """Vorgeschlagene Stellendaten, wie ein Importer sie liefert (noch nicht gespeichert)."""

    title: str
    company_name: str | None = None
    location: str | None = None
    remote_type: RemoteType = RemoteType.UNKNOWN
    description: str | None = None
    posted_at: datetime | None = None
    reference: SourceReference
    raw_payload: dict[str, Any] = Field(default_factory=dict)


class ImportNotSupportedError(NotImplementedError):
    pass


def parse_url(url: str) -> SplitResult:
    raw = url.strip()
    if "://" not in raw:
        raw = f"https://{raw}"
    parts = urlsplit(raw)
    if not parts.netloc:
        raise ValueError(f"Ungültige URL: {url!r}")
    return parts


def strip_tracking(parts: SplitResult) -> str:
    """Generische Normalisierung: Host klein, ohne Fragment und Tracking-Parameter."""
    query = [
        (k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith(_TRACKING_PREFIXES)
    ]
    host = parts.netloc.lower().removeprefix("www.")
    path = parts.path.rstrip("/") or "/"
    return urlunsplit(("https", host, path, urlencode(sorted(query)), ""))


class SourceAdapter(ABC):
    source: JobSource

    @abstractmethod
    def matches(self, parts: SplitResult) -> bool:
        """True, wenn die URL zu dieser Quelle gehört."""

    @abstractmethod
    def identify(self, parts: SplitResult) -> SourceReference:
        """Externe ID und normalisierte URL bestimmen, ohne Netzwerkzugriff."""

    async def fetch(self, reference: SourceReference) -> JobPostingDraft:
        """Stellendaten live laden. Wird in späteren Iterationen je Quelle implementiert."""
        raise ImportNotSupportedError(f"Import für {self.source} ist noch nicht verfügbar")
