"""Geschäftslogik für Bewerbungen: Statuswechsel (append-only), Notizen, Stammdaten."""

from __future__ import annotations

import logging
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from bewerbung.db.models import Application, ApplicationStatusEvent, Note
from bewerbung.db.types import utcnow
from bewerbung.domain.enums import ApplicationStatus
from bewerbung.domain.errors import InvalidTransitionError, NotFoundError
from bewerbung.domain.schemas import ApplicationUpdate, NoteCreate, StatusChange

logger = logging.getLogger(__name__)

_CLOCK_SKEW = timedelta(minutes=5)


def get_application(session: Session, application_id: int) -> Application:
    application = session.scalar(
        select(Application)
        .where(Application.id == application_id)
        .options(selectinload(Application.events), selectinload(Application.notes))
    )
    if application is None:
        raise NotFoundError("Bewerbung", application_id)
    return application


def change_status(session: Session, application_id: int, change: StatusChange) -> Application:
    """Neuen Status als Event anhängen und die Projektion ``current_status`` nachziehen.

    Rückdatieren ist erlaubt, aber nicht vor den letzten Wechsel: so bleibt die
    Event-Kette monoton und ``from_status`` stimmt immer.
    """
    application = get_application(session, application_id)
    now = utcnow()
    occurred_at = change.occurred_at or now

    if change.status is application.current_status:
        raise InvalidTransitionError(f"Status ist bereits '{change.status}'")
    if occurred_at > now + _CLOCK_SKEW:
        raise InvalidTransitionError("Statuswechsel darf nicht in der Zukunft liegen")
    if occurred_at < application.status_changed_at:
        raise InvalidTransitionError("Zeitpunkt liegt vor dem letzten Statuswechsel")

    event = ApplicationStatusEvent(
        from_status=application.current_status,
        to_status=change.status,
        note=change.note,
        occurred_at=occurred_at,
        recorded_at=now,
    )
    application.events.append(event)
    application.current_status = change.status
    application.status_changed_at = occurred_at
    if application.applied_at is None and change.status is not ApplicationStatus.SAVED:
        application.applied_at = occurred_at

    session.flush()
    logger.info("Bewerbung %s: %s -> %s", application.id, event.from_status, event.to_status)
    return application


def update_application(
    session: Session, application_id: int, data: ApplicationUpdate
) -> Application:
    application = get_application(session, application_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        if field == "priority" and value is None:
            continue
        setattr(application, field, value)
    session.flush()
    return application


def add_note(session: Session, application_id: int, data: NoteCreate) -> Note:
    application = get_application(session, application_id)
    note = Note(application=application, body=data.body)
    session.add(note)
    # Notiz zählt als Aktivität: Bewerbung in "zuletzt geändert" nach oben holen.
    application.updated_at = utcnow()
    application.posting.updated_at = application.updated_at
    session.flush()
    return note
