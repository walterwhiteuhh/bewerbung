"""Gemeinsame Typen für Anschreiben-Generatoren."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol

Tone = Literal["formell", "modern", "locker"]
Length = Literal["kurz", "normal", "ausfuehrlich"]

LENGTH_WORDS: dict[Length, str] = {
    "kurz": "180 bis 230 Wörter",
    "normal": "260 bis 340 Wörter",
    "ausfuehrlich": "380 bis 460 Wörter",
}


class GenerationError(Exception):
    """Generator konnte keinen Text liefern (Netzwerk, Ablehnung, Limit)."""


@dataclass(frozen=True, slots=True)
class LetterContext:
    """Alles, was ein Generator über Stelle und Bewerber:in wissen darf."""

    title: str
    company: str | None
    location: str | None
    portal: str | None  # Anzeigename, z. B. "StepStone"; None bei manueller Erfassung
    url: str | None
    description: str | None
    tags: list[str]
    employment_type: str | None
    remote: str | None
    contact_name: str | None
    applicant_name: str | None
    applicant_headline: str | None
    applicant_summary: str | None
    applicant_skills: list[str]
    cv_text: str | None
    signature: str | None
    tone: Tone = "modern"
    length: Length = "normal"
    extra_notes: str | None = None
    matching_skills: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class GeneratedLetter:
    body: str
    generator: str
    model: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None


class LetterGenerator(Protocol):
    name: str

    @property
    def unavailable_reason(self) -> str | None: ...

    def generate(self, ctx: LetterContext) -> GeneratedLetter: ...
