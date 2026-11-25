"""Arbeitgeberlogos der Arbeitsagentur, lokal zwischengespeichert.

Die Jobsuche-API liefert Logos nur mit ``X-API-Key``-Header, daher kann der Browser
sie nicht direkt laden. Der Server holt jedes Logo einmal und legt es neben der
Datenbank ab (``logos/``). Fehlende Logos werden ebenfalls vermerkt, damit die Liste
beim Scrollen nicht ständig dieselben 404-Anfragen auslöst.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

LOGO_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/ed/v1/arbeitgeberlogo/{hash}"
MAX_LOGO_BYTES = 512 * 1024
_HASH = re.compile(r"^[A-Za-z0-9_\-=]{6,128}$")
_MISSING_TTL = timedelta(days=7)
# Nur Rasterformate: SVG könnte beim direkten Öffnen Skripte ausführen.
_SIGNATURES: tuple[tuple[bytes, str, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"GIF8", "image/gif", ".gif"),
)

_EXTENSIONS = (*((t, e) for _, t, e in _SIGNATURES), ("image/webp", ".webp"))


@dataclass(frozen=True, slots=True)
class CachedLogo:
    path: Path
    media_type: str


def _sniff(data: bytes) -> tuple[str, str] | None:
    for magic, media_type, ext in _SIGNATURES:
        if data.startswith(magic):
            return media_type, ext
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp", ".webp"
    return None


def valid_hash(value: str) -> bool:
    return bool(_HASH.fullmatch(value))


class AaLogoCache:
    def __init__(
        self,
        directory: Path,
        api_key: str,
        timeout: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._dir = directory
        self._api_key = api_key
        self._timeout = timeout
        self._transport = transport

    def _cached(self, logo_hash: str) -> CachedLogo | None:
        for media_type, ext in _EXTENSIONS:
            path = self._dir / f"aa-{logo_hash}{ext}"
            if path.is_file():
                return CachedLogo(path, media_type)
        return None

    def _known_missing(self, logo_hash: str) -> bool:
        marker = self._dir / f"aa-{logo_hash}.none"
        if not marker.is_file():
            return False
        age = datetime.now(UTC) - datetime.fromtimestamp(marker.stat().st_mtime, UTC)
        return age < _MISSING_TTL

    async def get(self, logo_hash: str) -> CachedLogo | None:
        if not valid_hash(logo_hash):
            return None
        if (hit := self._cached(logo_hash)) is not None:
            return hit
        if self._known_missing(logo_hash):
            return None
        data = await self._download(logo_hash)
        if data is None:  # Netzwerkfehler: beim nächsten Aufruf erneut versuchen
            return None
        self._dir.mkdir(parents=True, exist_ok=True)
        sniffed = _sniff(data)
        if sniffed is None:  # 404, zu groß oder kein Bild: eine Woche lang nicht nachfragen
            (self._dir / f"aa-{logo_hash}.none").touch()
            return None
        media_type, ext = sniffed
        path = self._dir / f"aa-{logo_hash}{ext}"
        tmp = path.with_suffix(".part")
        tmp.write_bytes(data)
        tmp.replace(path)
        return CachedLogo(path, media_type)

    async def _download(self, logo_hash: str) -> bytes | None:
        headers = {"X-API-Key": self._api_key, "User-Agent": "Bewerbungsmanager/0.3"}
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout, transport=self._transport
            ) as client:
                resp = await client.get(LOGO_URL.format(hash=logo_hash), headers=headers)
        except httpx.HTTPError as exc:
            logger.info("AA-Logo %s nicht ladbar: %s", logo_hash, exc)
            return None
        if resp.status_code >= 500 or resp.status_code == 429:
            return None
        if resp.status_code != 200 or len(resp.content) > MAX_LOGO_BYTES:
            return b""
        return resp.content
