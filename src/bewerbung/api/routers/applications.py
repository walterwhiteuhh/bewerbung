"""Bewerbungen: Status (append-only), Stammdaten, Notizen."""

from __future__ import annotations

from fastapi import APIRouter, status

from bewerbung.api.deps import SessionDep
from bewerbung.domain.schemas import (
    ApplicationRead,
    ApplicationUpdate,
    NoteCreate,
    NoteRead,
    StatusChange,
)
from bewerbung.services import applications

router = APIRouter()


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
