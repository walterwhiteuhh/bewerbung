"""REST-Endpunkte unter ``/api``. Dünne Schicht: Validierung -> Service -> Schema."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query, status

from bewerbung.api.deps import RegistryDep, SessionDep
from bewerbung.domain.schemas import (
    ApplicationRead,
    ApplicationUpdate,
    NoteCreate,
    NoteRead,
    PostingCreate,
    PostingDetail,
    PostingFilter,
    PostingListItem,
    PostingPage,
    PostingUpdate,
    SourceDetection,
    Stats,
    StatusChange,
)
from bewerbung.services import applications, postings, stats

router = APIRouter(prefix="/api")


@router.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/sources/detect", response_model=SourceDetection, tags=["sources"])
def detect_source(
    session: SessionDep, registry: RegistryDep, url: Annotated[str, Query(min_length=4)]
) -> SourceDetection:
    """Quelle, externe ID und mögliche Dublette zu einer eingefügten URL bestimmen."""
    return postings.detect_source(session, registry, url)


# --- Stellen -----------------------------------------------------------------


@router.get("/postings", response_model=PostingPage, tags=["postings"])
def list_postings(session: SessionDep, flt: Annotated[PostingFilter, Query()]) -> PostingPage:
    """Filter: ``q`` (Freitext), ``status``/``source`` (mehrfach), Sortierung, Paginierung."""
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


# --- Bewerbungen -------------------------------------------------------------


@router.get("/applications/{application_id}", response_model=ApplicationRead, tags=["applications"])
def get_application(session: SessionDep, application_id: int) -> ApplicationRead:
    return ApplicationRead.model_validate(applications.get_application(session, application_id))


@router.patch(
    "/applications/{application_id}", response_model=ApplicationRead, tags=["applications"]
)
def update_application(
    session: SessionDep, application_id: int, data: ApplicationUpdate
) -> ApplicationRead:
    return ApplicationRead.model_validate(
        applications.update_application(session, application_id, data)
    )


@router.post(
    "/applications/{application_id}/status",
    response_model=ApplicationRead,
    tags=["applications"],
)
def change_status(session: SessionDep, application_id: int, data: StatusChange) -> ApplicationRead:
    return ApplicationRead.model_validate(applications.change_status(session, application_id, data))


@router.post(
    "/applications/{application_id}/notes",
    response_model=NoteRead,
    status_code=status.HTTP_201_CREATED,
    tags=["applications"],
)
def add_note(session: SessionDep, application_id: int, data: NoteCreate) -> NoteRead:
    return NoteRead.model_validate(applications.add_note(session, application_id, data))


# --- Statistik ---------------------------------------------------------------


@router.get("/stats", response_model=Stats, tags=["stats"])
def get_stats(session: SessionDep) -> Stats:
    return stats.compute_stats(session)
