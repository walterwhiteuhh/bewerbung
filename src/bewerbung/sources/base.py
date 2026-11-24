"""Schnittstelle für Quellen (LinkedIn, Stepstone, ...).

``identify`` leitet aus einer URL Quelle, externe ID und normalisierte URL ab
(Dublettenschutz, ohne Netzwerk). ``fetch_url`` bestimmt, welche Seite der
Import lädt; das Extrahieren übernimmt ``sources.extract`` für alle Quellen gemeinsam.
Eine Quelle mit offizieller API kann später einen eigenen Importer bekommen.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from urllib.parse import SplitResult, parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import BaseModel, ConfigDict

from bewerbung.domain.enums import JobSource

_TRACKING_PREFIXES = ("utm_", "trk", "ref", "src", "cmp", "gclid", "fbclid", "mc_")


class SourceReference(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: JobSource
    external_id: str | None = None
    url_normalized: str


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

    def fetch_url(self, reference: SourceReference, original_url: str) -> str:
        """Welche Seite für den Import geladen wird. Adapter können eine stabilere URL wählen."""
        return original_url
