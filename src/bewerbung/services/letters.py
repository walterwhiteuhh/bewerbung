"""Bewerberprofil pflegen und Anschreiben zu einer Stelle erzeugen."""

from __future__ import annotations

import logging
import re
import time
from dataclasses import asdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bewerbung.db.models import ApplicantProfile, CoverLetter, JobPosting
from bewerbung.domain.enums import JobSource, RemoteType
from bewerbung.domain.errors import DomainError, LetterGenerationError, NotFoundError
from bewerbung.domain.keywords import suggest_tags
from bewerbung.domain.schemas import (
    CoverLetterRead,
    CoverLetterRequest,
    CoverLetterUpdate,
    GeneratorInfo,
    LetterContextPreview,
    ProfileUpdate,
)
from bewerbung.letters.base import GenerationError, LetterContext, LetterGenerator
from bewerbung.letters.prompt import PROMPT_VERSION
from bewerbung.services.postings import get_posting

logger = logging.getLogger(__name__)

# Wie das Portal im Brief heißen darf. Bewerbermanagement-Systeme sind Karriereseiten.
PORTAL_NAMES: dict[JobSource, str] = {
    JobSource.LINKEDIN: "LinkedIn",
    JobSource.STEPSTONE: "StepStone",
    JobSource.XING: "XING",
    JobSource.INDEED: "Indeed",
    JobSource.ARBEITSAGENTUR: "der Jobbörse der Bundesagentur für Arbeit",
    JobSource.GLASSDOOR: "Glassdoor",
    JobSource.ADZUNA: "Adzuna",
    JobSource.PERSONIO: "Ihrer Karriereseite",
    JobSource.GREENHOUSE: "Ihrer Karriereseite",
    JobSource.LEVER: "Ihrer Karriereseite",
    JobSource.SOFTGARDEN: "Ihrer Karriereseite",
    JobSource.JOIN: "JOIN",
    JobSource.WORKDAY: "Ihrer Karriereseite",
}
_REMOTE_NAMES = {
    RemoteType.REMOTE: "Remote",
    RemoteType.HYBRID: "Hybrid",
    RemoteType.ONSITE: "Vor Ort",
}
GENERATOR_LABELS = {
    "claude": "Claude",
    "openai": "ChatGPT",
    "gemini": "Gemini",
    "template": "Vorlage",
}

# Lange Beschreibungen kappen: genug Kontext, ohne unnötig Tokens zu verbrauchen.
_MAX_DESCRIPTION_CHARS = 12_000


# --- Profil ------------------------------------------------------------------


def get_profile(session: Session) -> ApplicantProfile:
    profile = session.scalar(select(ApplicantProfile).order_by(ApplicantProfile.id).limit(1))
    if profile is None:
        profile = ApplicantProfile(skills=[])
        session.add(profile)
        session.flush()
    return profile


def update_profile(session: Session, data: ProfileUpdate) -> ApplicantProfile:
    profile = get_profile(session)
    for key, value in data.model_dump().items():
        setattr(profile, key, value)
    session.flush()
    return profile


def _missing_profile_fields(profile: ApplicantProfile) -> list[str]:
    checks = {
        "Name": profile.full_name,
        "Kurzprofil": profile.headline,
        "Über mich oder Lebenslauf": profile.summary or profile.cv_text,
    }
    return [label for label, value in checks.items() if not value]


# --- Kontext -----------------------------------------------------------------


def _matching_skills(skills: list[str], tags: list[str], text: str) -> list[str]:
    """Profil-Skills, die in Hashtags oder Beschreibung vorkommen (Reihenfolge des Profils)."""
    lowered_tags = {t.casefold() for t in tags}
    hits = []
    for skill in skills:
        # "Machine Learning" trifft auch "Machine-Learning-Modelle" (Leerzeichen = Bindestrich).
        core = r"[\s-]+".join(re.escape(w) for w in skill.split())
        pattern = rf"(?<![\w])(?:{core})(?![\w])"
        tag_form = "-".join(skill.casefold().split())
        if (
            skill.casefold() in lowered_tags
            or tag_form in lowered_tags
            or re.search(pattern, text, re.IGNORECASE)
        ):
            hits.append(skill)
    return hits


def _suggested(posting: JobPosting) -> list[str]:
    return suggest_tags(
        title=posting.title,
        description=posting.description,
        location=posting.location,
        remote_type=posting.remote_type,
        employment_type=posting.employment_type,
    )


def build_context(session: Session, posting: JobPosting, req: CoverLetterRequest) -> LetterContext:
    profile = get_profile(session)
    app = posting.application
    # Hashtags der Stelle; fehlen sie, die automatisch erkannten verwenden.
    tags = posting.tags or _suggested(posting)
    description = posting.description
    if description and len(description) > _MAX_DESCRIPTION_CHARS:
        description = description[:_MAX_DESCRIPTION_CHARS].rstrip() + " …"
    return LetterContext(
        title=posting.title,
        company=posting.company.name if posting.company else None,
        location=posting.location,
        portal=PORTAL_NAMES.get(posting.source),
        url=posting.url,
        description=description,
        tags=tags,
        employment_type=posting.employment_type,
        remote=_REMOTE_NAMES.get(posting.remote_type),
        contact_name=app.contact_name if app else None,
        applicant_name=profile.full_name,
        applicant_headline=profile.headline,
        applicant_summary=profile.summary,
        applicant_skills=list(profile.skills),
        cv_text=profile.cv_text,
        signature=profile.signature,
        tone=req.tone,
        length=req.length,
        extra_notes=req.extra_notes,
        matching_skills=_matching_skills(
            list(profile.skills), tags, f"{posting.title}\n{posting.description or ''}"
        ),
    )


def preview_context(session: Session, posting_id: int) -> LetterContextPreview:
    posting = get_posting(session, posting_id)
    profile = get_profile(session)
    ctx = build_context(session, posting, CoverLetterRequest())
    missing = _missing_profile_fields(profile)
    excerpt = (posting.description or "").strip()
    return LetterContextPreview(
        portal=ctx.portal,
        tags=posting.tags,
        suggested_tags=[
            t
            for t in _suggested(posting)
            if t.casefold() not in {x.casefold() for x in posting.tags}
        ],
        description_excerpt=(excerpt[:400] + " …") if len(excerpt) > 400 else (excerpt or None),
        matching_skills=ctx.matching_skills,
        profile_complete=not missing,
        missing_profile_fields=missing,
    )


# --- Generatoren -------------------------------------------------------------


def generator_infos(generators: dict[str, LetterGenerator]) -> list[GeneratorInfo]:
    return [
        GeneratorInfo(
            name=name,
            label=GENERATOR_LABELS.get(name, name),
            available=gen.unavailable_reason is None,
            reason=gen.unavailable_reason,
            model=getattr(gen, "model", None),
        )
        for name, gen in generators.items()
    ]


def _pick_generator(generators: dict[str, LetterGenerator], wanted: str) -> LetterGenerator:
    if wanted != "auto":
        gen = generators.get(wanted)
        if gen is None:
            raise DomainError(f"Unbekannter Generator: {wanted}")
        if reason := gen.unavailable_reason:
            raise DomainError(f"{GENERATOR_LABELS.get(wanted, wanted)} nicht verfügbar: {reason}")
        return gen
    for gen in generators.values():
        if gen.unavailable_reason is None:
            return gen
    raise DomainError("Kein Generator verfügbar")


def _snapshot(ctx: LetterContext) -> dict[str, Any]:
    return asdict(ctx)


def generate_letter(
    session: Session,
    generators: dict[str, LetterGenerator],
    posting_id: int,
    req: CoverLetterRequest,
) -> CoverLetter:
    posting = get_posting(session, posting_id)
    ctx = build_context(session, posting, req)
    generator = _pick_generator(generators, req.generator)
    started = time.perf_counter()
    try:
        result = generator.generate(ctx)
    except GenerationError as exc:
        raise LetterGenerationError(f"Anschreiben konnte nicht erstellt werden: {exc}") from exc
    duration_ms = int((time.perf_counter() - started) * 1000)

    next_version = (
        session.scalar(
            select(func.max(CoverLetter.version)).where(CoverLetter.posting_id == posting.id)
        )
        or 0
    ) + 1
    app = posting.application
    letter = CoverLetter(
        posting_id=posting.id,
        application_id=app.id if app else None,
        version=next_version,
        status="draft",
        body=result.body,
        body_generated=result.body,
        generator=result.generator,
        model=result.model,
        prompt_version=PROMPT_VERSION if result.generator == "claude" else "template",
        tone=req.tone,
        input_snapshot={**_snapshot(ctx), "length": req.length},
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
        duration_ms=duration_ms,
    )
    session.add(letter)
    session.flush()
    logger.info(
        "Anschreiben v%s für Stelle %s erstellt (%s, %d ms)",
        next_version,
        posting.id,
        result.generator,
        duration_ms,
    )
    return letter


def list_letters(session: Session, posting_id: int) -> list[CoverLetter]:
    get_posting(session, posting_id)  # 404, falls es die Stelle nicht gibt
    return list(
        session.scalars(
            select(CoverLetter)
            .where(CoverLetter.posting_id == posting_id)
            .order_by(CoverLetter.version.desc())
        )
    )


def get_letter(session: Session, letter_id: int) -> CoverLetter:
    letter = session.get(CoverLetter, letter_id)
    if letter is None:
        raise NotFoundError("Anschreiben", letter_id)
    return letter


def update_letter(session: Session, letter_id: int, data: CoverLetterUpdate) -> CoverLetter:
    letter = get_letter(session, letter_id)
    if data.body is not None:
        letter.body = data.body
    if data.status is not None:
        if data.status == "final":
            # Pro Stelle gibt es höchstens eine finale Fassung.
            for other in list_letters(session, letter.posting_id):
                if other.id != letter.id and other.status == "final":
                    other.status = "draft"
        letter.status = data.status
    session.flush()
    return letter


def to_read(letter: CoverLetter) -> CoverLetterRead:
    return CoverLetterRead(
        id=letter.id,
        posting_id=letter.posting_id,
        version=letter.version,
        status=letter.status,
        body=letter.body,
        edited=letter.body != letter.body_generated,
        generator=letter.generator,
        model=letter.model,
        tone=letter.tone,
        input_snapshot=letter.input_snapshot,
        created_at=letter.created_at,
        updated_at=letter.updated_at,
    )
