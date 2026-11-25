"""Hashtags: Normalisierung und Erkennung in Freitext."""

from __future__ import annotations

import re

MAX_TAG_LENGTH = 40

# Ein Hashtag beginnt mit Buchstabe/Ziffer und darf "-", "_" und "." enthalten,
# endet aber nicht mit Satzzeichen ("#python." -> "python").
_HASHTAG_RE = re.compile(r"(?<![\w#])#(\w[\w\-.]*\w|\w)", re.UNICODE)
_VALID_RE = re.compile(r"^\w[\w\-.]*$", re.UNICODE)


def clean_tag(raw: str) -> str:
    """Anzeigename: führende "#" und Leerraum weg, innere Leerzeichen werden zu "-".

    Wirft ``ValueError`` bei leeren oder ungültigen Namen.
    """
    name = re.sub(r"\s+", "-", raw.strip().lstrip("#").strip()).strip("-.")
    if not name:
        raise ValueError("Hashtag darf nicht leer sein")
    if len(name) > MAX_TAG_LENGTH:
        raise ValueError(f"Hashtag darf höchstens {MAX_TAG_LENGTH} Zeichen haben")
    if not _VALID_RE.match(name):
        raise ValueError(f"Ungültiger Hashtag: {raw!r} (erlaubt: Buchstaben, Ziffern, - _ .)")
    return name


def tag_key(name: str) -> str:
    """Vergleichsschlüssel, über den "Python", "python" und "#PYTHON" zusammenfallen."""
    return clean_tag(name).casefold()


def unique_tags(names: list[str]) -> list[str]:
    """Bereinigt und entfernt Dubletten (erste Schreibweise gewinnt), Reihenfolge bleibt."""
    seen: dict[str, str] = {}
    for raw in names:
        name = clean_tag(raw)
        seen.setdefault(name.casefold(), name)
    return list(seen.values())


def extract_hashtags(text: str) -> list[str]:
    """Alle #hashtags aus Freitext, bereinigt und ohne Dubletten."""
    found = [m.group(1) for m in _HASHTAG_RE.finditer(text)]
    return unique_tags([t for t in found if len(t) <= MAX_TAG_LENGTH])
