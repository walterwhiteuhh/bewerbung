"""Stellendaten aus HTML extrahieren, ohne externe Parser-Abhängigkeit.

Reihenfolge der Quellen (stabil -> fragil):
1. schema.org ``JobPosting`` als JSON-LD (Stepstone, viele Karriereseiten, teils LinkedIn)
2. OpenGraph-/Meta-Tags als Fallback für Titel und Beschreibung

Das Ergebnis enthält immer die verwendeten Rohdaten, damit sie in ``raw_payload``
gespeichert und später erneut (z. B. mit besserem Parser oder NLP) ausgewertet werden können.
"""

from __future__ import annotations

import json
import logging
import re
from datetime import UTC, date, datetime
from html import unescape
from html.parser import HTMLParser
from typing import Any

from pydantic import BaseModel, Field

from bewerbung.domain.enums import RemoteType

logger = logging.getLogger(__name__)

EXTRACTOR_VERSION = "1"

_BLOCK_TAGS = {"p", "div", "br", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "tr"}
_PERIOD_FACTOR = {"YEAR": 1, "MONTH": 12, "WEEK": 52}


class ExtractedPosting(BaseModel):
    title: str | None = None
    company_name: str | None = None
    location: str | None = None
    remote_type: RemoteType = RemoteType.UNKNOWN
    employment_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    description: str | None = None
    posted_at: datetime | None = None
    method: str = Field(description="'json-ld', 'opengraph' oder 'none'")
    raw: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_empty(self) -> bool:
        return self.title is None and self.company_name is None


class _PageParser(HTMLParser):
    """Sammelt JSON-LD-Blöcke, Meta-Tags und den <title>."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.json_ld: list[str] = []
        self.meta: dict[str, str] = {}
        self.title = ""
        self._in_ld = False
        self._in_title = False
        self._buf: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "script" and a.get("type", "").lower() == "application/ld+json":
            self._in_ld, self._buf = True, []
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            key = (a.get("property") or a.get("name") or "").lower()
            if key and "content" in a:
                self.meta.setdefault(key, a["content"])

    def handle_endtag(self, tag: str) -> None:
        if tag == "script" and self._in_ld:
            self.json_ld.append("".join(self._buf))
            self._in_ld = False
        elif tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_ld:
            self._buf.append(data)
        elif self._in_title:
            self.title += data


class _TextParser(HTMLParser):
    """HTML-Beschreibung -> lesbarer Text mit Absätzen und Aufzählungszeichen."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "li":
            self.parts.append("\n• ")
        elif tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in _BLOCK_TAGS and tag != "li":
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        self.parts.append(data)


def html_to_text(value: str) -> str:
    parser = _TextParser()
    parser.feed(unescape(value) if "&lt;" in value else value)
    text = "".join(parser.parts)
    lines = [re.sub(r"[ \t\u00a0]+", " ", line).strip() for line in text.splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def _iter_nodes(data: Any) -> list[dict[str, Any]]:
    """JSON-LD kann Objekt, Liste oder @graph sein."""
    if isinstance(data, list):
        return [n for item in data for n in _iter_nodes(item)]
    if isinstance(data, dict):
        nodes = [data]
        if isinstance(data.get("@graph"), list):
            nodes += _iter_nodes(data["@graph"])
        return nodes
    return []


def _is_job_posting(node: dict[str, Any]) -> bool:
    types = node.get("@type")
    types = types if isinstance(types, list) else [types]
    return "JobPosting" in types


def _first(value: Any) -> Any:
    return value[0] if isinstance(value, list) and value else value


def _text(value: Any) -> str | None:
    value = _first(value)
    if isinstance(value, dict):
        value = value.get("name")
    if isinstance(value, str | int | float):
        cleaned = " ".join(unescape(str(value)).split())
        return cleaned or None
    return None


def _location(node: dict[str, Any]) -> str | None:
    places = node.get("jobLocation")
    places = places if isinstance(places, list) else [places]
    cities: list[str] = []
    for place in places:
        if not isinstance(place, dict):
            continue
        address = place.get("address")
        if isinstance(address, dict):
            city = _text(address.get("addressLocality")) or _text(address.get("addressRegion"))
        else:
            city = _text(address)
        if city and city not in cities:
            cities.append(city)
    return ", ".join(cities) or None


def _remote(node: dict[str, Any]) -> RemoteType:
    loc_type = json.dumps(node.get("jobLocationType", "")).upper()
    if "TELECOMMUTE" in loc_type:
        return RemoteType.HYBRID if node.get("jobLocation") else RemoteType.REMOTE
    return RemoteType.UNKNOWN


def _employment(node: dict[str, Any]) -> str | None:
    labels = {
        "FULL_TIME": "Vollzeit",
        "PART_TIME": "Teilzeit",
        "CONTRACTOR": "Freiberuflich",
        "TEMPORARY": "Befristet",
        "INTERN": "Praktikum",
        "VOLUNTEER": "Ehrenamt",
        "PER_DIEM": "Tageweise",
    }
    raw = node.get("employmentType")
    values = raw if isinstance(raw, list) else [raw]
    out = [labels.get(str(v).upper(), str(v)) for v in values if v]
    return ", ".join(out) or None


def _salary(node: dict[str, Any]) -> tuple[int | None, int | None, str | None]:
    base = _first(node.get("baseSalary"))
    if not isinstance(base, dict):
        return None, None, None
    currency = _text(base.get("currency"))
    value = base.get("value")
    if not isinstance(value, dict):
        value = {"value": value}
    factor = _PERIOD_FACTOR.get(str(value.get("unitText", "YEAR")).upper())
    if factor is None:  # Stundenlöhne o. ä. nicht in Jahresgehalt umrechnen
        return None, None, currency

    def num(key: str) -> int | None:
        try:
            return round(float(value[key]) * factor) if value.get(key) is not None else None
        except (TypeError, ValueError):
            return None

    lo = num("minValue") or num("value")
    hi = num("maxValue") or (num("value") if lo is not None and num("minValue") is None else None)
    return lo, hi, currency.upper()[:3] if currency else None


def _date(value: Any) -> datetime | None:
    text = _text(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            parsed = datetime.combine(date.fromisoformat(text[:10]), datetime.min.time())
        except ValueError:
            return None
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _from_json_ld(node: dict[str, Any]) -> ExtractedPosting:
    lo, hi, currency = _salary(node)
    description = node.get("description")
    return ExtractedPosting(
        title=_text(node.get("title")) or _text(node.get("name")),
        company_name=_text(node.get("hiringOrganization")),
        location=_location(node),
        remote_type=_remote(node),
        employment_type=_employment(node),
        salary_min=lo,
        salary_max=hi,
        salary_currency=currency,
        description=html_to_text(description) if isinstance(description, str) else None,
        posted_at=_date(node.get("datePosted")),
        method="json-ld",
        raw={"json_ld": node},
    )


def _from_meta(meta: dict[str, str], page_title: str) -> ExtractedPosting:
    title = meta.get("og:title") or page_title.strip() or None
    description = meta.get("og:description") or meta.get("description")
    return ExtractedPosting(
        title=" ".join(title.split()) if title else None,
        description=html_to_text(description) if description else None,
        method="opengraph" if title else "none",
        raw={"meta": {k: v for k, v in meta.items() if k.startswith(("og:", "description"))}},
    )


def extract_posting(html: str) -> ExtractedPosting:
    parser = _PageParser()
    parser.feed(html)

    for block in parser.json_ld:
        try:
            data = json.loads(block.strip())
        except json.JSONDecodeError:
            logger.debug("Ungültiges JSON-LD übersprungen")
            continue
        for node in _iter_nodes(data):
            if _is_job_posting(node):
                return _from_json_ld(node)

    return _from_meta(parser.meta, parser.title)
