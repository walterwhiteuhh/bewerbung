"""Fachliche Wertebereiche. Als ``StrEnum``, damit sie in DB, JSON und UI identisch sind."""

from __future__ import annotations

from enum import StrEnum
from typing import Literal


class JobSource(StrEnum):
    MANUAL = "manual"
    LINKEDIN = "linkedin"
    STEPSTONE = "stepstone"
    XING = "xing"
    INDEED = "indeed"
    ARBEITSAGENTUR = "arbeitsagentur"
    GLASSDOOR = "glassdoor"
    # Bewerbermanagement-Systeme (Karriereseiten vieler Firmen)
    PERSONIO = "personio"
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    SOFTGARDEN = "softgarden"
    JOIN = "join"
    WORKDAY = "workday"
    # Aggregatoren mit offizieller Such-API
    ADZUNA = "adzuna"
    JOOBLE = "jooble"
    ARBEITNOW = "arbeitnow"
    REMOTIVE = "remotive"
    OTHER = "other"


class RemoteType(StrEnum):
    ONSITE = "onsite"
    HYBRID = "hybrid"
    REMOTE = "remote"
    UNKNOWN = "unknown"


class ApplicationStatus(StrEnum):
    SAVED = "saved"  # Gemerkt
    APPLIED = "applied"  # Beworben
    IN_REVIEW = "in_review"  # In Prüfung / Rückmeldung
    INTERVIEW = "interview"
    OFFER = "offer"
    ACCEPTED = "accepted"
    REJECTED = "rejected"  # Absage
    WITHDRAWN = "withdrawn"  # Zurückgezogen

    @property
    def is_terminal(self) -> bool:
        return self in {
            ApplicationStatus.ACCEPTED,
            ApplicationStatus.REJECTED,
            ApplicationStatus.WITHDRAWN,
        }

    @property
    def funnel_rank(self) -> int:
        """Ordnung im Bewerbungs-Funnel; Endzustände ohne Fortschritt erhalten -1."""
        return _FUNNEL.get(self, -1)


_FUNNEL: dict[ApplicationStatus, int] = {
    ApplicationStatus.SAVED: 0,
    ApplicationStatus.APPLIED: 1,
    ApplicationStatus.IN_REVIEW: 2,
    ApplicationStatus.INTERVIEW: 3,
    ApplicationStatus.OFFER: 4,
    ApplicationStatus.ACCEPTED: 5,
}


class OutcomeReason(StrEnum):
    """Strukturierter Grund für einen Endzustand (Label für spätere Modelle)."""

    NO_RESPONSE = "no_response"  # nie Rückmeldung bekommen
    REJECTED_SCREENING = "rejected_screening"  # Absage nach Unterlagen
    REJECTED_INTERVIEW = "rejected_interview"  # Absage nach Gespräch
    POSITION_FILLED = "position_filled"
    SALARY_MISMATCH = "salary_mismatch"
    LOCATION_MISMATCH = "location_mismatch"
    BETTER_OFFER = "better_offer"
    OWN_DECISION = "own_decision"  # selbst abgesagt / Interesse verloren
    OTHER = "other"


# Filter der Portalsuche (Arbeitszeit, Angebotsart).
WorkTime = Literal["vollzeit", "teilzeit", "minijob", "schicht"]
OfferType = Literal["arbeit", "ausbildung", "praktikum", "selbststaendig"]

WORK_TIME_LABEL: dict[str, str] = {
    "vollzeit": "Vollzeit",
    "teilzeit": "Teilzeit",
    "minijob": "Minijob",
    "schicht": "Schicht/Nacht/Wochenende",
}
