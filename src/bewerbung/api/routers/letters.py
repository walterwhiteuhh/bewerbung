"""Bewerberprofil und Anschreiben."""

from __future__ import annotations

from fastapi import APIRouter, status

from bewerbung.api.deps import LetterGeneratorsDep, SessionDep
from bewerbung.domain.schemas import (
    CoverLetterRead,
    CoverLetterRequest,
    CoverLetterUpdate,
    GeneratorInfo,
    LetterContextPreview,
    ProfileRead,
    ProfileUpdate,
)
from bewerbung.services import insights, letters

router = APIRouter()


@router.get("/profile", response_model=ProfileRead, tags=["letters"])
def get_profile(session: SessionDep) -> ProfileRead:
    return ProfileRead.model_validate(letters.get_profile(session))


@router.put("/profile", response_model=ProfileRead, tags=["letters"])
def put_profile(session: SessionDep, data: ProfileUpdate) -> ProfileRead:
    profile = letters.update_profile(session, data)
    insights.locate_home(session, profile, None)
    return ProfileRead.model_validate(profile)


@router.get("/letters/generators", response_model=list[GeneratorInfo], tags=["letters"])
def list_generators(generators: LetterGeneratorsDep) -> list[GeneratorInfo]:
    return letters.generator_infos(generators)


@router.get(
    "/postings/{posting_id}/letter-context", response_model=LetterContextPreview, tags=["letters"]
)
def letter_context(session: SessionDep, posting_id: int) -> LetterContextPreview:
    """Automatisch erkannte Grundlagen (Portal, Hashtags, Beschreibung, passende Skills)."""
    return letters.preview_context(session, posting_id)


@router.get(
    "/postings/{posting_id}/letters", response_model=list[CoverLetterRead], tags=["letters"]
)
def list_letters(session: SessionDep, posting_id: int) -> list[CoverLetterRead]:
    return [letters.to_read(x) for x in letters.list_letters(session, posting_id)]


@router.post(
    "/postings/{posting_id}/letters",
    response_model=CoverLetterRead,
    status_code=status.HTTP_201_CREATED,
    tags=["letters"],
)
def create_letter(
    session: SessionDep,
    generators: LetterGeneratorsDep,
    posting_id: int,
    data: CoverLetterRequest,
) -> CoverLetterRead:
    """Erzeugt eine neue Version. Läuft synchron (Claude braucht ggf. einige Sekunden)."""
    return letters.to_read(letters.generate_letter(session, generators, posting_id, data))


@router.patch("/letters/{letter_id}", response_model=CoverLetterRead, tags=["letters"])
def patch_letter(session: SessionDep, letter_id: int, data: CoverLetterUpdate) -> CoverLetterRead:
    return letters.to_read(letters.update_letter(session, letter_id, data))
