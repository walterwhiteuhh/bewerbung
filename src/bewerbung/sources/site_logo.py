"""Firmenlogo von der Website holen und lokal ablegen.

Ablauf: Startseite laden -> ``<link rel="apple-touch-icon"|"icon">`` auswerten ->
bestes Bild laden -> inhaltsadressiert in ``data/logos/`` speichern. Es werden nur die
Startseite und höchstens ``MAX_IMAGE_TRIES`` Bild-URLs abgerufen; jede Weiterleitung wird
erneut gegen interne Adressen geprüft (SSRF-Schutz wie beim Anzeigen-Import).
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit

import httpx

from bewerbung.domain.socials import socials_from_html
from bewerbung.sources.fetcher import USER_AGENT, FetchError, assert_public_host

logger = logging.getLogger(__name__)

MAX_PAGE_BYTES = 2 * 1024 * 1024
MAX_IMAGE_BYTES = 512 * 1024
MAX_IMAGE_TRIES = 4
MAX_REDIRECTS = 5
FILE_NAME = re.compile(r"^[0-9a-f]{64}\.(png|jpg|gif|webp|ico|svg)$")
MEDIA_TYPES = {
    "png": "image/png",
    "jpg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "ico": "image/x-icon",
    "svg": "image/svg+xml",
}


_SIGNATURES: tuple[tuple[bytes, int, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", 0, "png"),
    (b"\xff\xd8\xff", 0, "jpg"),
    (b"GIF8", 0, "gif"),
    (b"WEBP", 8, "webp"),  # nach "RIFF" + Länge
    (b"\x00\x00\x01\x00", 0, "ico"),
)


def sniff_image(data: bytes) -> str | None:
    """Dateiendung anhand der Magic Bytes; None, wenn es kein unterstütztes Bild ist."""
    for magic, offset, ext in _SIGNATURES:
        if data[offset : offset + len(magic)] == magic:
            return ext
    head = data[:512].lstrip()
    if head.startswith((b"<svg", b"<?xml")) and b"<svg" in data[:2048]:
        return "svg"
    return None


class _IconParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.icons: list[tuple[int, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "link":
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        rel = set(a.get("rel", "").lower().split())
        href = a.get("href", "").strip()
        if not href or href.startswith("data:"):
            return
        size = max((int(n) for n in re.findall(r"(\d+)x\d+", a.get("sizes", ""))), default=0)
        if rel & {"apple-touch-icon", "apple-touch-icon-precomposed"}:
            self.icons.append((1000 + (size or 180), href))
        elif "icon" in rel:
            is_svg = href.lower().split("?")[0].endswith(".svg") or "svg" in a.get("type", "")
            self.icons.append((500 if is_svg else 100 + size, href))


def icon_candidates(html: str, base_url: str) -> list[str]:
    """Bild-URLs in absteigender Güte, inkl. der üblichen Standardpfade als Rückfall."""
    parser = _IconParser()
    try:
        parser.feed(html)
    except Exception:
        logger.debug("HTML der Startseite nicht vollständig lesbar")
    ranked = [urljoin(base_url, href) for _, href in sorted(parser.icons, key=lambda x: -x[0])]
    ranked += [urljoin(base_url, "/apple-touch-icon.png"), urljoin(base_url, "/favicon.ico")]
    seen: set[str] = set()
    out: list[str] = []
    for url in ranked:
        if urlsplit(url).scheme in {"http", "https"} and url not in seen:
            seen.add(url)
            out.append(url)
    return out


@dataclass(frozen=True, slots=True)
class StoredLogo:
    name: str
    media_type: str


class LogoStore:
    """Inhaltsadressierte Ablage: gleiche Bilder werden nur einmal gespeichert."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def save(self, data: bytes) -> StoredLogo:
        ext = sniff_image(data)
        if ext is None:
            raise ValueError("Kein unterstütztes Bildformat")
        name = f"{hashlib.sha256(data).hexdigest()}.{ext}"
        path = self.directory / name
        if not path.is_file():
            self.directory.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(".part")
            tmp.write_bytes(data)
            tmp.replace(path)
        return StoredLogo(name, MEDIA_TYPES[ext])

    def path(self, name: str) -> Path | None:
        if not FILE_NAME.fullmatch(name):
            return None
        path = self.directory / name
        return path if path.is_file() else None


@dataclass(frozen=True, slots=True)
class SiteInfo:
    logo: bytes | None
    socials: dict[str, str] = field(default_factory=dict)


class SiteLogoFetcher:
    def __init__(
        self,
        timeout: float = 10.0,
        check_host: bool = True,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._timeout = timeout
        self._check_host = check_host
        self._transport = transport

    async def fetch_logo(self, website: str) -> bytes:
        """Bestes Logo der Website als Bytes; FetchError mit Nutzerhinweis, wenn keins da ist."""
        site = await self.fetch_site(website)
        if site.logo is None:
            raise FetchError("Auf der Website wurde kein Logo gefunden")
        return site.logo

    async def fetch_site(self, website: str) -> SiteInfo:
        """Startseite einmal laden: Logo (falls vorhanden) und Social-Media-Profile."""
        async with httpx.AsyncClient(
            timeout=self._timeout,
            headers={"User-Agent": USER_AGENT, "Accept-Language": "de-DE,de;q=0.9"},
            follow_redirects=False,
            transport=self._transport,
        ) as client:
            try:
                final_url, page = await self._get(client, website, MAX_PAGE_BYTES)
            except FetchError:
                final_url, page = website, b""  # Standardpfade trotzdem versuchen
            html = page.decode("utf-8", errors="replace")
            socials = socials_from_html(html, final_url)
            for url in icon_candidates(html, final_url)[:MAX_IMAGE_TRIES]:
                try:
                    _, data = await self._get(client, url, MAX_IMAGE_BYTES)
                except FetchError as exc:
                    logger.debug("Logo-Kandidat %s verworfen: %s", url, exc)
                    continue
                if sniff_image(data) is not None:
                    logger.info("Logo gefunden: %s (%d Bytes)", url, len(data))
                    return SiteInfo(logo=data, socials=socials)
        return SiteInfo(logo=None, socials=socials)

    async def _get(self, client: httpx.AsyncClient, url: str, limit: int) -> tuple[str, bytes]:
        current = url
        for _ in range(MAX_REDIRECTS + 1):
            if self._check_host:
                await assert_public_host(current)
            try:
                async with client.stream("GET", current) as resp:
                    if resp.is_redirect and "location" in resp.headers:
                        current = urljoin(current, resp.headers["location"])
                        continue
                    if resp.status_code >= 400:
                        raise FetchError(f"Fehler {resp.status_code}")
                    body = bytearray()
                    async for chunk in resp.aiter_bytes():
                        body += chunk
                        if len(body) > limit:
                            raise FetchError("Datei zu groß")
                    return current, bytes(body)
            except httpx.HTTPError as exc:
                raise FetchError(f"Website nicht erreichbar: {exc}") from exc
        raise FetchError("Zu viele Weiterleitungen")
