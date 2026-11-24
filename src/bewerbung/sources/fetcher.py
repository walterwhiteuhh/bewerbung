"""HTTP-Abruf einzelner Anzeigen-Seiten.

Bewusst defensiv: nur http(s), keine privaten/lokalen Ziele (SSRF-Schutz, da die App
URLs aus Nutzereingaben lädt), Timeout, Größenlimit, Redirects mit erneuter Prüfung.
Es wird immer nur die eine, vom Nutzer angegebene Seite geladen; kein Crawling.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from typing import Protocol
from urllib.parse import urljoin, urlsplit

import httpx

logger = logging.getLogger(__name__)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36 Bewerbungsmanager/0.2"
)
MAX_BYTES = 3 * 1024 * 1024
MAX_REDIRECTS = 5


class FetchError(Exception):
    """Seite nicht ladbar; die Meldung ist für Nutzer gedacht."""


class PageFetcher(Protocol):
    async def fetch(self, url: str) -> str: ...


async def _assert_public_host(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise FetchError("Nur http- und https-Adressen können geladen werden")
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(parts.hostname, None)
    except socket.gaierror as exc:
        raise FetchError(f"Adresse {parts.hostname} nicht gefunden") from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise FetchError("Interne oder lokale Adressen werden nicht geladen")


class HttpPageFetcher:
    def __init__(self, timeout: float = 10.0, check_host: bool = True) -> None:
        self._timeout = timeout
        self._check_host = check_host

    async def fetch(self, url: str) -> str:
        headers = {"User-Agent": USER_AGENT, "Accept-Language": "de-DE,de;q=0.9,en;q=0.6"}
        async with httpx.AsyncClient(
            timeout=self._timeout, headers=headers, follow_redirects=False, trust_env=True
        ) as client:
            current = url
            for _ in range(MAX_REDIRECTS + 1):
                if self._check_host:
                    await _assert_public_host(current)
                try:
                    async with client.stream("GET", current) as resp:
                        if resp.is_redirect and "location" in resp.headers:
                            current = urljoin(current, resp.headers["location"])
                            continue
                        if resp.status_code in {401, 403, 429, 999}:
                            raise FetchError(
                                "Die Seite verweigert den automatischen Abruf"
                                f" ({resp.status_code}),"
                                " bitte Daten manuell eintragen"
                            )
                        if resp.status_code >= 400:
                            raise FetchError(f"Die Seite antwortet mit Fehler {resp.status_code}")
                        body = bytearray()
                        async for chunk in resp.aiter_bytes():
                            body += chunk
                            if len(body) > MAX_BYTES:
                                raise FetchError("Die Seite ist zu groß")
                        logger.info("Seite geladen: %s (%d Bytes)", current, len(body))
                        return body.decode(resp.encoding or "utf-8", errors="replace")
                except httpx.TimeoutException as exc:
                    raise FetchError("Zeitüberschreitung beim Laden der Seite") from exc
                except httpx.HTTPError as exc:
                    raise FetchError(f"Seite konnte nicht geladen werden: {exc}") from exc
            raise FetchError("Zu viele Weiterleitungen")
