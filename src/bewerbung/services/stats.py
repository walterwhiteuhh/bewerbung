"""Kennzahlen; Aggregation läuft per GROUP BY in der Datenbank."""

from __future__ import annotations

from sqlalchemy import distinct, func, select
from sqlalchemy.orm import Session

from bewerbung.db.models import Application, ApplicationStatusEvent, JobPosting
from bewerbung.domain.enums import ApplicationStatus
from bewerbung.domain.schemas import CountBucket, Stats

_RESPONSE_STATUSES = (
    ApplicationStatus.IN_REVIEW,
    ApplicationStatus.INTERVIEW,
    ApplicationStatus.OFFER,
    ApplicationStatus.ACCEPTED,
    ApplicationStatus.REJECTED,
)


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

    return Stats(
        total=total,
        active=active,
        by_status=by_status,
        by_source=by_source,
        response_rate=round(responded / applied, 3) if applied else None,
    )
