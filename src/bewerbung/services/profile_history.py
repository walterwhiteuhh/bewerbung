"""Verlauf des Bewerberprofils (append-only).

``applicant_profiles`` wird überschrieben. Jede inhaltliche Änderung hängt hier einen
Schnappschuss an, und Bewerbungen merken sich beim Absenden den dann gültigen Stand.
So lässt sich später rekonstruieren, mit welchem Profil (Skills, Lebenslauf, Wohnort)
eine Bewerbung rausging, ohne Data Leakage durch spätere Änderungen.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from bewerbung.db.models import ApplicantProfile, ApplicantProfileVersion

TRACKED_FIELDS = (
    "full_name",
    "email",
    "phone",
    "address",
    "headline",
    "summary",
    "skills",
    "cv_text",
    "home_location",
    "home_lat",
    "home_lon",
    "max_distance_km",
    "signature",
)


def snapshot_of(profile: ApplicantProfile) -> dict[str, Any]:
    return {f: getattr(profile, f) for f in TRACKED_FIELDS}


def _hash(snapshot: dict[str, Any]) -> str:
    raw = json.dumps(snapshot, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def latest_version(session: Session, profile_id: int) -> ApplicantProfileVersion | None:
    return session.scalar(
        select(ApplicantProfileVersion)
        .where(ApplicantProfileVersion.profile_id == profile_id)
        .order_by(ApplicantProfileVersion.id.desc())
        .limit(1)
    )


def record_version(session: Session, profile: ApplicantProfile) -> ApplicantProfileVersion | None:
    """Neue Version nur, wenn sich der Inhalt gegenüber der letzten geändert hat."""
    if profile.id is None:
        session.flush()
    snap = snapshot_of(profile)
    digest = _hash(snap)
    last = latest_version(session, profile.id)
    if last is not None and last.content_hash == digest:
        return None
    version = ApplicantProfileVersion(profile_id=profile.id, content_hash=digest, snapshot=snap)
    session.add(version)
    session.flush()
    return version


def current_version_id(session: Session) -> int | None:
    """Id des aktuellen Profilstands; ``None``, wenn noch kein Profil angelegt wurde."""
    profile = session.scalar(select(ApplicantProfile).order_by(ApplicantProfile.id).limit(1))
    if profile is None:
        return None
    version = latest_version(session, profile.id) or record_version(session, profile)
    return version.id if version else None
