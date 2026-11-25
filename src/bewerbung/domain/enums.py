"""Fachliche Wertebereiche. Als ``StrEnum``, damit sie in DB, JSON und UI identisch sind."""

from __future__ import annotations

from enum import StrEnum


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
