"""Stellen: Liste, Anlegen, Bearbeiten, Archivieren."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from bewerbung.api.deps import RegistryDep, SessionDep
from bewerbung.domain.schemas import (
    PostingCreate,
    PostingDetail,
    PostingFilter,
    PostingListItem,
    PostingPage,
    PostingUpdate,
)
from bewerbung.services import postings

router = APIRouter()


@router.get("/postings", response_model=PostingPage, tags=["postings"])
def list_postings(session: SessionDep, flt: Annotated[PostingFilter, Query()]) -> PostingPage:
    """Filter: ``q`` (Freitext), ``status``/``source``/``tag`` (mehrfach), Sortierung, Paginierung.

    Mehrere ``tag``-Werte sind UND-verknüpft: nur Stellen, die alle Hashtags tragen.
    """
    items, total = postings.list_postings(session, flt)
    return PostingPage(
        items=[PostingListItem.model_validate(p) for p in items],
        total=total,
        limit=flt.limit,
        offset=flt.offset,
    )


@router.post(
    "/postings",
    response_model=PostingDetail,
    status_code=status.HTTP_201_CREATED,
    tags=["postings"],
)
def create_posting(
    session: SessionDep, registry: RegistryDep, data: PostingCreate
) -> PostingDetail:
    posting = postings.create_posting(session, registry, data)
    return PostingDetail.model_validate(postings.get_posting(session, posting.id))


@router.get("/postings/{posting_id}", response_model=PostingDetail, tags=["postings"])
def get_posting(session: SessionDep, posting_id: int) -> PostingDetail:
    return PostingDetail.model_validate(postings.get_posting(session, posting_id))


@router.patch("/postings/{posting_id}", response_model=PostingDetail, tags=["postings"])
def update_posting(
    session: SessionDep, registry: RegistryDep, posting_id: int, data: PostingUpdate
) -> PostingDetail:
    postings.update_posting(session, registry, posting_id, data)
    return PostingDetail.model_validate(postings.get_posting(session, posting_id))


@router.post("/postings/{posting_id}/archive", response_model=PostingDetail, tags=["postings"])
def archive_posting(session: SessionDep, posting_id: int) -> PostingDetail:
    """Soft-Delete: die Stelle verschwindet aus Listen, die Historie bleibt erhalten."""
    return PostingDetail.model_validate(postings.set_archived(session, posting_id, archived=True))


@router.post("/postings/{posting_id}/restore", response_model=PostingDetail, tags=["postings"])
def restore_posting(session: SessionDep, posting_id: int) -> PostingDetail:
    return PostingDetail.model_validate(postings.set_archived(session, posting_id, archived=False))
