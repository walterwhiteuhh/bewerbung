"""Hashtag-Vorschläge aus Stellendaten (regelbasiert, ohne Netzwerk).

Bewusst einfach: ein kuratiertes Vokabular mit Mustern. Die Vorschläge landen in
``posting_tags`` mit ``origin = "auto"``; ob Nutzer sie behalten oder entfernen,
ist später ein Label, um das Vokabular oder ein Modell zu verbessern.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

from bewerbung.domain.enums import RemoteType
from bewerbung.domain.tags import clean_tag

MAX_SUGGESTIONS = 10

# Kanonischer Hashtag -> Regex (case-insensitive, an Wortgrenzen).
_VOCABULARY: dict[str, str] = {
    "python": r"python",
    "java": r"java(?!script)",
    "javascript": r"javascript|\bjs\b",
    "typescript": r"typescript",
    "react": r"react(?:\.js)?",
    "angular": r"angular",
    "vue": r"vue(?:\.js)?",
    "node": r"node(?:\.js)?",
    "dotnet": r"\.net|c#|asp\.net",
    "golang": r"golang",
    "rust": r"\brust\b",
    "php": r"\bphp\b",
    "sql": r"\bsql\b|postgres(?:ql)?|mysql|t-sql",
    "nosql": r"nosql|mongodb|cassandra",
    "spark": r"\bspark\b|pyspark|databricks",
    "pandas": r"pandas",
    "machine-learning": r"machine[\s-]learning|\bml\b|maschinelles\s+lernen",
    "ki": r"\bki\b|künstliche\s+intelligenz|\bai\b|artificial\s+intelligence",
    "llm": r"\bllms?\b|large\s+language\s+model|generative\s+ai|genai",
    "nlp": r"\bnlp\b|natural\s+language",
    "data-science": r"data[\s-]scien\w*",
    "data-engineering": r"data[\s-]engineer\w*",
    "bi": r"business\s+intelligence|\bbi\b",
    "power-bi": r"power\s?bi",
    "tableau": r"tableau",
    "excel": r"\bexcel\b",
    "sap": r"\bsap\b",
    "aws": r"\baws\b|amazon\s+web\s+services",
    "azure": r"\bazure\b",
    "gcp": r"\bgcp\b|google\s+cloud",
    "cloud": r"\bcloud\b",
    "docker": r"docker",
    "kubernetes": r"kubernetes|\bk8s\b",
    "devops": r"devops|ci/cd",
    "linux": r"linux",
    "scrum": r"scrum",
    "agil": r"\bagil(?:e|en)?\b|\bagile\b",
    "projektmanagement": r"projektmanagement|project\s+management",
    "consulting": r"consulting|beratung",
    "english": r"englisch|english",
}
_COMPILED = {
    tag: re.compile(rf"(?<![\w])(?:{pat})(?![\w])", re.IGNORECASE)
    for tag, pat in _VOCABULARY.items()
}

_LEVELS = {
    "werkstudent": re.compile(r"werkstudent|working\s+student", re.IGNORECASE),
    "praktikum": re.compile(r"praktik(?:um|ant)|internship", re.IGNORECASE),
    "junior": re.compile(r"\bjunior\b|berufseinst", re.IGNORECASE),
    "senior": re.compile(r"\bsenior\b", re.IGNORECASE),
    "lead": re.compile(r"\blead\b|teamleit|head\s+of", re.IGNORECASE),
}

_REMOTE_TAG = {RemoteType.REMOTE: "remote", RemoteType.HYBRID: "hybrid"}


def _city_tag(location: str | None) -> str | None:
    if not location:
        return None
    city = re.split(r"[,(/]", location, maxsplit=1)[0].strip()
    city = re.sub(r"^\d{5}\s+", "", city)  # "20095 Hamburg" -> "Hamburg"
    try:
        return clean_tag(city).lower()
    except ValueError:
        return None


def suggest_tags(
    *,
    title: str | None,
    description: str | None,
    location: str | None = None,
    remote_type: RemoteType = RemoteType.UNKNOWN,
    employment_type: str | None = None,
) -> list[str]:
    """Vorschläge, wichtigste zuerst: Level, Arbeitsmodell, Ort, dann Skills nach Häufigkeit."""
    title = title or ""
    text = f"{title}\n{description or ''}"
    tags: list[str] = []

    tags += [tag for tag, rx in _LEVELS.items() if rx.search(title)]
    if remote_type in _REMOTE_TAG:
        tags.append(_REMOTE_TAG[remote_type])
    if employment_type and re.search(r"teilzeit|part", employment_type, re.IGNORECASE):
        tags.append("teilzeit")
    if city := _city_tag(location):
        tags.append(city)

    # Treffer im Titel zählen dreifach: die Kernanforderung steht meist dort.
    scored = [
        (len(rx.findall(text)) + 2 * len(rx.findall(title)), tag) for tag, rx in _COMPILED.items()
    ]
    tags += [tag for score, tag in sorted(scored, key=lambda s: (-s[0], s[1])) if score > 0]
    return _dedupe(tags)[:MAX_SUGGESTIONS]


def _dedupe(tags: Iterable[str]) -> list[str]:
    seen: dict[str, str] = {}
    for t in tags:
        seen.setdefault(t.casefold(), t)
    return list(seen.values())
