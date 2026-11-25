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

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bewerbung.db.models import ApplicantProfile, ApplicantProfileVersion, Application
from bewerbung.domain.schemas import ProfileVersionRead

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
    # Vergleich über die verfolgten Felder (nicht über den gespeicherten Hash): ältere
    # Schnappschüsse enthalten evtl. abgeleitete Felder wie Koordinaten, die nichts bedeuten.
    if last is not None and {f: last.snapshot.get(f) for f in TRACKED_FIELDS} == snap:
        return None
    version = ApplicantProfileVersion(profile_id=profile.id, content_hash=digest, snapshot=snap)
    session.add(version)
    session.flush()
    return version


def list_history(session: Session) -> list[ProfileVersionRead]:
    """Profilstände, neueste zuerst: was sich gegenüber dem Vorgänger geändert hat und mit
    wie vielen Bewerbungen der Stand rausging (``applications.profile_version_id``)."""
    versions = list(
        session.scalars(
            select(ApplicantProfileVersion).order_by(
                ApplicantProfileVersion.profile_id, ApplicantProfileVersion.id
            )
        )
    )
    counts = dict(
        session.execute(
            select(Application.profile_version_id, func.count())
            .where(Application.profile_version_id.is_not(None))
            .group_by(Application.profile_version_id)
        ).all()
    )
    out: list[ProfileVersionRead] = []
    previous: dict[str, Any] = {}
    previous_profile: int | None = None
    for v in versions:
        before = previous if previous_profile == v.profile_id else {}
        now = {f: v.snapshot.get(f) for f in TRACKED_FIELDS}
        changed = [
            f for f in TRACKED_FIELDS if now[f] != before.get(f) and (now[f] or before.get(f))
        ]
        old_skills, new_skills = set(before.get("skills") or []), set(now["skills"] or [])
        out.append(
            ProfileVersionRead(
                id=v.id,
                created_at=v.created_at,
                is_first=not before,
                changed_fields=changed,
                skills_added=sorted(new_skills - old_skills, key=str.casefold),
                skills_removed=sorted(old_skills - new_skills, key=str.casefold),
                application_count=counts.get(v.id, 0),
            )
        )
        previous, previous_profile = now, v.profile_id
    return out[::-1]


def current_version_id(session: Session) -> int | None:
    """Id des aktuellen Profilstands; ``None``, wenn noch kein Profil angelegt wurde."""
    profile = session.scalar(select(ApplicantProfile).order_by(ApplicantProfile.id).limit(1))
    if profile is None:
        return None
    version = latest_version(session, profile.id) or record_version(session, profile)
    return version.id if version else None
