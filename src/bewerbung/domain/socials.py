"""Social-Media-Profile von Firmen erkennen (aus JSON-LD ``sameAs`` und Website-Links).

Reine Funktionen ohne Netzwerk. Ergebnis ist immer ``{netz: kanonische_url}``,
je Netz höchstens ein Profil; Teilen-/Like-Links und einzelne Beiträge zählen nicht.
"""

from __future__ import annotations

import contextlib
import re
from collections.abc import Callable, Iterable, Mapping
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

# Reihenfolge = Anzeige-Reihenfolge (beruflich relevante Netze zuerst).
NETWORKS: tuple[str, ...] = (
    "linkedin",
    "xing",
    "kununu",
    "instagram",
    "facebook",
    "youtube",
    "x",
    "tiktok",
    "github",
)

_HANDLE = re.compile(r"^@?[\w.\-]{2,80}$")
_RESERVED = frozenset(
    {
        "share", "sharer", "sharer.php", "intent", "dialog", "plugins", "login", "signup",
        "home", "hashtag", "search", "explore", "accounts", "p", "reel", "reels", "stories",
        "watch", "embed", "results", "shorts", "privacy", "legal", "about", "help", "tr",
        "settings", "i", "events", "groups", "pages", "people", "feed", "jobs", "messages",
    }
)  # fmt: skip


def _segments(path: str) -> list[str]:
    return [s for s in path.split("/") if s]


def _handle(segs: list[str], *, at: bool = False) -> str | None:
    if not segs:
        return None
    first = segs[0]
    if first.lower() in _RESERVED or not _HANDLE.fullmatch(first):
        return None
    if at and not first.startswith("@"):
        return None
    return first


def _linkedin(segs: list[str]) -> str | None:
    if len(segs) >= 2 and segs[0] in {"company", "school", "showcase"}:
        return f"https://www.linkedin.com/{segs[0]}/{segs[1]}"
    return None


def _xing(segs: list[str]) -> str | None:
    if len(segs) >= 2 and segs[0] in {"pages", "companies", "company"}:
        return f"https://www.xing.com/{segs[0]}/{segs[1]}"
    return None


def _kununu(segs: list[str]) -> str | None:
    # kununu.com/de/<firma>[/kommentare]
    if len(segs) >= 2 and len(segs[0]) == 2:
        return f"https://www.kununu.com/{segs[0]}/{segs[1]}"
    return None


def _youtube(segs: list[str]) -> str | None:
    if len(segs) >= 2 and segs[0] in {"channel", "c", "user"}:
        return f"https://www.youtube.com/{segs[0]}/{segs[1]}"
    h = _handle(segs, at=True)
    return f"https://www.youtube.com/{h}" if h else None


def _simple(base: str, *, at: bool = False) -> Callable[[list[str]], str | None]:
    def build(segs: list[str]) -> str | None:
        h = _handle(segs, at=at)
        return f"{base}/{h}" if h else None

    return build


_HOSTS: dict[str, tuple[str, Callable[[list[str]], str | None]]] = {
    "linkedin.com": ("linkedin", _linkedin),
    "xing.com": ("xing", _xing),
    "kununu.com": ("kununu", _kununu),
    "instagram.com": ("instagram", _simple("https://www.instagram.com")),
    "facebook.com": ("facebook", _simple("https://www.facebook.com")),
    "youtube.com": ("youtube", _youtube),
    "x.com": ("x", _simple("https://x.com")),
    "twitter.com": ("x", _simple("https://x.com")),
    "tiktok.com": ("tiktok", _simple("https://www.tiktok.com", at=True)),
    "github.com": ("github", _simple("https://github.com")),
}


def classify_social(url: str | None) -> tuple[str, str] | None:
    """URL -> (netz, kanonische Profil-URL) oder None."""
    if not url or not isinstance(url, str):
        return None
    raw = url.strip()
    if "://" not in raw:
        raw = f"https://{raw}"
    parts = urlsplit(raw)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        return None
    host = parts.hostname.lower()
    for suffix, (network, build) in _HOSTS.items():
        if host == suffix or host.endswith(f".{suffix}"):
            canonical = build(_segments(parts.path))
            return (network, canonical) if canonical else None
    return None


def collect_socials(urls: Iterable[Any]) -> dict[str, str]:
    found: dict[str, str] = {}
    for url in urls:
        hit = classify_social(url) if isinstance(url, str) else None
        if hit and hit[0] not in found:
            found[hit[0]] = hit[1]
    return order_socials(found)


def order_socials(links: Mapping[str, str]) -> dict[str, str]:
    return {n: links[n] for n in NETWORKS if links.get(n)}


def merge_socials(existing: Mapping[str, str] | None, new: Mapping[str, str]) -> dict[str, str]:
    """Bekannte Profile bleiben, neue Netze kommen dazu."""
    return order_socials({**new, **(existing or {})})


def socials_from_payload(raw: Any) -> dict[str, str]:
    """``hiringOrganization.sameAs``/``url`` aus JSON-LD."""
    if not isinstance(raw, dict):
        return {}
    node = raw.get("json_ld") if isinstance(raw.get("json_ld"), dict) else raw
    org = node.get("hiringOrganization") if isinstance(node, dict) else None
    if isinstance(org, list):
        org = org[0] if org else None
    if not isinstance(org, dict):
        return {}
    urls: list[Any] = []
    for key in ("sameAs", "url"):
        value = org.get(key)
        urls.extend(value if isinstance(value, list) else [value])
    return collect_socials(urls)


class _LinkParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in {"a", "link"}:
            href = dict(attrs).get("href")
            if href:
                self.hrefs.append(href)


def socials_from_html(html: str, base_url: str) -> dict[str, str]:
    """Profil-Links aus Kopf/Fußzeile einer Firmen-Website."""
    parser = _LinkParser()
    # Kaputtes HTML liefert, was bis dahin gelesen wurde.
    with contextlib.suppress(Exception):
        parser.feed(html)
    return collect_socials(urljoin(base_url, h) for h in parser.hrefs)
