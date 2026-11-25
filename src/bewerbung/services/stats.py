"""Kennzahlen; Aggregation läuft per GROUP BY in der Datenbank."""

from __future__ import annotations

from datetime import timedelta
from statistics import median
from typing import Any

from sqlalchemy import Select, SQLColumnExpression, distinct, func, select
from sqlalchemy.orm import Session

from bewerbung.db.models import Application, ApplicationStatusEvent, JobPosting
from bewerbung.db.types import utcnow
from bewerbung.domain.enums import ApplicationStatus
from bewerbung.domain.schemas import CountBucket, SalaryStat, Stats

_RESPONSE_STATUSES = (
    ApplicationStatus.IN_REVIEW,
    ApplicationStatus.INTERVIEW,
    ApplicationStatus.OFFER,
    ApplicationStatus.ACCEPTED,
    ApplicationStatus.REJECTED,
)


def _latest_labelled_events(column: SQLColumnExpression[Any]) -> Select[Any]:
    """Je Bewerbung das zuletzt erfasste Ereignis, das ``column`` gesetzt hat (aktive Stellen).

    Events sind append-only und ``change_status`` hält ``occurred_at`` monoton, daher
    entspricht die höchste ID dem jüngsten Ereignis.
    """
    latest = (
        select(func.max(ApplicationStatusEvent.id))
        .where(column.is_not(None))
        .group_by(ApplicationStatusEvent.application_id)
        .scalar_subquery()
    )
    return (
        select(ApplicationStatusEvent)
        .join(Application, Application.id == ApplicationStatusEvent.application_id)
        .join(JobPosting, JobPosting.id == Application.posting_id)
        .where(JobPosting.archived_at.is_(None), ApplicationStatusEvent.id.in_(latest))
    )


def _reason_buckets(session: Session) -> list[CountBucket]:
    ev = _latest_labelled_events(ApplicationStatusEvent.reason_code).subquery()
    rows = session.execute(
        select(ev.c.reason_code, func.count())
        .group_by(ev.c.reason_code)
        .order_by(func.count().desc(), ev.c.reason_code)
    ).all()
    return [CountBucket(key=reason, count=count) for reason, count in rows]


def _salary_stats(session: Session) -> list[SalaryStat]:
    ev = _latest_labelled_events(ApplicationStatusEvent.offered_salary).subquery()
    by_currency: dict[str, list[int]] = {}
    for currency, salary in session.execute(select(ev.c.offered_currency, ev.c.offered_salary)):
        by_currency.setdefault(currency or "EUR", []).append(salary)
    stats = [
        SalaryStat(currency=cur, count=len(v), min=min(v), median=round(median(v)), max=max(v))
        for cur, v in by_currency.items()
    ]
    return sorted(stats, key=lambda x: (-x.count, x.currency))


def compute_stats(session: Session) -> Stats:
    active_postings = JobPosting.archived_at.is_(None)

    by_status_rows = session.execute(
        select(Application.current_status, func.count())
        .join(JobPosting, JobPosting.id == Application.posting_id)
        .where(active_postings)
        .group_by(Application.current_status)
    ).all()
    status_counts = {status: count for status, count in by_status_rows}
    by_status = [CountBucket(key=s.value, count=status_counts.get(s, 0)) for s in ApplicationStatus]

    by_source = [
        CountBucket(key=source.value, count=count)
        for source, count in session.execute(
            select(JobPosting.source, func.count())
            .where(active_postings)
            .group_by(JobPosting.source)
            .order_by(func.count().desc())
        ).all()
    ]

    total = sum(status_counts.values())
    active = sum(c for s, c in status_counts.items() if not s.is_terminal)

    applied = (
        session.scalar(
            select(func.count())
            .select_from(Application)
            .join(JobPosting, JobPosting.id == Application.posting_id)
            .where(active_postings, Application.applied_at.is_not(None))
        )
        or 0
    )
    responded = (
        session.scalar(
            select(func.count(distinct(ApplicationStatusEvent.application_id)))
            .join(Application, Application.id == ApplicationStatusEvent.application_id)
            .join(JobPosting, JobPosting.id == Application.posting_id)
            .where(
                active_postings,
                Application.applied_at.is_not(None),
                ApplicationStatusEvent.to_status.in_(_RESPONSE_STATUSES),
            )
        )
        or 0
    )

    # Aktivität fürs "Wetter" der Startseite: wie viel hat sich zuletzt bewegt?
    events = (
        select(
            func.count().filter(ApplicationStatusEvent.occurred_at >= utcnow() - timedelta(days=7)),
            func.max(ApplicationStatusEvent.occurred_at),
        )
        .join(Application, Application.id == ApplicationStatusEvent.application_id)
        .join(JobPosting, JobPosting.id == Application.posting_id)
        .where(active_postings)
    )
    activity_7d, last_activity_at = session.execute(events).one()

    return Stats(
        total=total,
        active=active,
        by_status=by_status,
        by_source=by_source,
        response_rate=round(responded / applied, 3) if applied else None,
        activity_7d=activity_7d or 0,
        last_activity_at=last_activity_at,
        by_reason=_reason_buckets(session),
        offer_salaries=_salary_stats(session),
    )
