"""Hilfen, die mehrere Such-Provider teilen."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from bewerbung.sources.extract import html_to_text

_MAX_DESCRIPTION = 20_000


def clean_html(value: Any) -> str | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = html_to_text(value) if "<" in value else value
    return text[:_MAX_DESCRIPTION].strip() or None


def parse_datetime(value: Any) -> datetime | None:
    """ISO-8601 (mit/ohne Zeitzone) oder Unix-Sekunden -> UTC."""
    if isinstance(value, int | float):
        return datetime.fromtimestamp(value, tz=UTC)
    if not isinstance(value, str) or not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


def query_terms(query: str) -> list[str]:
    return [t for t in re.split(r"[\s,]+", query.casefold()) if len(t) >= 2]


def matches_all(terms: Iterable[str], *fields: Any) -> bool:
    """Alle Suchbegriffe kommen irgendwo in den Feldern vor (für Quellen ohne Suchparameter)."""
    haystack = " ".join(
        " ".join(map(str, f)) if isinstance(f, list) else str(f or "") for f in fields
    ).casefold()
    return all(t in haystack for t in terms)
