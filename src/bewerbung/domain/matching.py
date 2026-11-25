"""Schlüssel und Ähnlichkeit für Querbezüge (Firma, gleiche Stelle, ähnliche Stellen).

Alles regelbasiert und ohne Netzwerk. Die Schlüssel (``company_key``, ``title_key``)
werden in der DB gespeichert und indiziert; die Ähnlichkeit wird zur Laufzeit über
eine kleine Kandidatenmenge berechnet. Ein späteres Embedding-Modell kann ``similarity``
ersetzen, ohne dass sich Schema oder API ändern.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from bewerbung.domain.enums import RemoteType
from bewerbung.domain.keywords import suggest_tags

# Unverändert lassen: companies.name_key ist mit genau diesem Muster gespeichert.
_LEGAL_FORMS = re.compile(r"\b(gmbh|ag|se|kg|ohg|ug|mbh|co|inc|ltd|llc|e\.?v)\b\.?", re.IGNORECASE)
# "(m/w/d)", "(w/m/d)", "(all genders)", "m/w/d", "*in", "(gn)" ...
_GENDER = re.compile(
    r"\(?\b(?:[mwdfx]\s*/\s*){1,3}[mwdfx]\b\)?|\((?:all genders?|gn\*?|d)\)|\*in(?:nen)?\b",
    re.IGNORECASE,
)
_STOPWORDS = frozenset(
    {
        "und",
        "oder",
        "der",
        "die",
        "das",
        "für",
        "fuer",
        "in",
        "im",
        "am",
        "an",
        "mit",
        "bei",
        "zum",
        "zur",
        "von",
        "als",
        "auf",
        "aus",
        "ab",
        "and",
        "or",
        "the",
        "for",
        "of",
        "at",
        "with",
        "to",
        "a",
        "job",
        "stelle",
        "mitarbeiter",
        "mitarbeiterin",
        "vollzeit",
        "teilzeit",
        "minijob",
        "befristet",
        "unbefristet",
        "sofort",
        "deutschland",
        "remote",
    }
)
_TOKEN = re.compile(r"[a-zäöüß0-9+#]+")


def company_key(name: str) -> str:
    """Normalisierter Vergleichsschlüssel: ohne Rechtsform, Satzzeichen und Mehrfach-Leerzeichen."""
    key = _LEGAL_FORMS.sub(" ", name.casefold())
    key = re.sub(r"[^\w]+", " ", key)
    return " ".join(key.split()) or name.casefold().strip()


def title_key(title: str) -> str:
    """'Data Engineer (m/w/d) - Hamburg' und 'Data Engineer m/w/d' -> 'data engineer hamburg'."""
    text = _GENDER.sub(" ", title.casefold())
    return " ".join(_TOKEN.findall(text))[:255]


def title_tokens(title: str) -> frozenset[str]:
    return frozenset(
        t
        for t in _TOKEN.findall(_GENDER.sub(" ", title.casefold()))
        if t not in _STOPWORDS and len(t) > 1
    )


@dataclass(frozen=True, slots=True)
class JobProfile:
    """Merkmale einer Stelle für den Vergleich (aus Posting oder Listing)."""

    title_tokens: frozenset[str]
    skills: frozenset[str]

    @classmethod
    def build(
        cls,
        title: str,
        description: str | None = None,
        tags: Iterable[str] = (),
        remote_type: RemoteType = RemoteType.UNKNOWN,
    ) -> JobProfile:
        auto = suggest_tags(title=title, description=description, remote_type=remote_type)
        skills = {t.casefold() for t in (*auto, *tags)}
        return cls(title_tokens(title), frozenset(skills))


@dataclass(frozen=True, slots=True)
class Similarity:
    score: float
    shared_title: tuple[str, ...]
    shared_skills: tuple[str, ...]


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def similarity(a: JobProfile, b: JobProfile) -> Similarity:
    """Gewichtete Jaccard-Ähnlichkeit: Titel 60 %, Skills/Hashtags 40 %."""
    score = 0.6 * _jaccard(a.title_tokens, b.title_tokens) + 0.4 * _jaccard(a.skills, b.skills)
    return Similarity(
        round(score, 3),
        tuple(sorted(a.title_tokens & b.title_tokens)),
        tuple(sorted(a.skills & b.skills)),
    )
