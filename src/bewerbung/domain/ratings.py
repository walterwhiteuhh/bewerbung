"""Arbeitgeber-Bewertungen: Normalisierung und Mittelwert über Bewertungsportale.

Reine Funktionen ohne Netzwerk. kununu, Glassdoor und Indeed sperren automatische Abrufe
(Bot-Prüfung), daher werden Werte von Hand mit Quelle und Anzahl erfasst.
Alle Werte werden auf eine 5er-Skala gebracht; der Gesamtwert ist das arithmetische
Mittel der Portale mit genügend Bewertungen.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

MIN_REVIEWS = 10  # je Portal, damit ein Wert in den Mittelwert eingeht
SCALE = 5.0


class RatingSource(StrEnum):
    KUNUNU = "kununu"
    GLASSDOOR = "glassdoor"
    INDEED = "indeed"
    GOOGLE = "google"
    OTHER = "other"


@dataclass(frozen=True, slots=True)
class RatingValue:
    source: str
    rating: float  # bereits auf 0..5 normalisiert
    review_count: int | None


@dataclass(frozen=True, slots=True)
class EmployerScore:
    mean: float | None  # None = zu wenige Bewertungen
    sources: list[str]  # Portale, die in den Mittelwert eingehen
    review_count: int  # Summe der Bewertungen dieser Portale
    min_reviews: int
    current: list[Any] = field(default_factory=list)  # aktuellster Wert je Portal


def normalize(value: float, scale_max: float = SCALE) -> float:
    """Beliebige Skala (5, 10, 100 …) auf 0..5 bringen."""
    if scale_max <= 0:
        raise ValueError("Skala muss positiv sein")
    if not 0 <= value <= scale_max:
        raise ValueError(f"Wert {value} liegt nicht zwischen 0 und {scale_max}")
    return round(value / scale_max * SCALE, 2)


def aggregate(values: Iterable[RatingValue], min_reviews: int = MIN_REVIEWS) -> EmployerScore:
    """Arithmetisches Mittel über Portale mit mindestens ``min_reviews`` Bewertungen.

    Je Portal zählt ein Wert (der aktuellste wird vorher ausgewählt). Ein Portal mit vielen
    Bewertungen bekommt bewusst kein höheres Gewicht, damit kein einzelnes Portal dominiert.
    """
    used = [v for v in values if v.review_count is not None and v.review_count >= min_reviews]
    if not used:
        return EmployerScore(mean=None, sources=[], review_count=0, min_reviews=min_reviews)
    return EmployerScore(
        mean=round(sum(v.rating for v in used) / len(used), 2),
        sources=sorted(v.source for v in used),
        review_count=sum(v.review_count or 0 for v in used),
        min_reviews=min_reviews,
    )
