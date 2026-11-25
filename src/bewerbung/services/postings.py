"""Geschäftslogik für Stellenanzeigen."""

from __future__ import annotations

import logging
from typing import Any, TypeVar

from sqlalchemy import ColumnElement, Select, SQLColumnExpression, and_, exists, func, or_, select
from sqlalchemy.orm import Session, selectinload

from bewerbung.db.models import (
    Application,
    ApplicationStatusEvent,
    Company,
    JobPosting,
    Listing,
    PostingTag,
    Tag,
)
from bewerbung.db.types import utcnow
from bewerbung.domain.enums import ApplicationStatus, JobSource
from bewerbung.domain.errors import DuplicatePostingError, NotFoundError
from bewerbung.domain.schemas import (
    PostingCreate,
    PostingFilter,
    PostingUpdate,
    SourceDetection,
)
from bewerbung.domain.tags import tag_key
from bewerbung.services.companies import get_or_create_company
from bewerbung.services.tags import add_tags, set_tags
from bewerbung.sources import SourceReference, SourceRegistry

logger = logging.getLogger(__name__)

_RowT = TypeVar("_RowT")


def find_duplicate(
    session: Session, source: JobSource, external_id: str | None, url_normalized: str | None
) -> int | None:
    conditions: list[ColumnElement[bool]] = []
    if external_id:
        conditions.append(and_(JobPosting.source == source, JobPosting.external_id == external_id))
    if url_normalized:
        conditions.append(JobPosting.url_normalized == url_normalized)
    if not conditions:
        return None
    return session.scalar(select(JobPosting.id).where(or_(*conditions)).limit(1))


def detect_source(session: Session, registry: SourceRegistry, url: str) -> SourceDetection:
    ref = registry.identify(url)
    return SourceDetection(
        source=ref.source,
        external_id=ref.external_id,
        url_normalized=ref.url_normalized,
        duplicate_of=find_duplicate(session, ref.source, ref.external_id, ref.url_normalized),
    )


def create_posting(
    session: Session,
    registry: SourceRegistry,
    data: PostingCreate,
    *,
    with_listing: bool = True,
) -> JobPosting:
    ref: SourceReference | None = registry.identify(data.url) if data.url else None
    source = data.source or (ref.source if ref else JobSource.MANUAL)
    external_id = data.external_id or (ref.external_id if ref else None)
    url_normalized = ref.url_normalized if ref else None

    if (existing := find_duplicate(session, source, external_id, url_normalized)) is not None:
        raise DuplicatePostingError(existing)

    posting = JobPosting(
        title=data.title,
        company=get_or_create_company(session, data.company_name) if data.company_name else None,
        location=data.location,
        remote_type=data.remote_type,
        employment_type=data.employment_type,
        salary_min=data.salary_min,
        salary_max=data.salary_max,
        salary_currency=data.salary_currency.upper(),
        description=data.description,
        source=source,
        external_id=external_id,
        url=data.url,
        url_normalized=url_normalized,
        raw_payload=data.raw_payload,
        posted_at=data.posted_at,
    )
    now = utcnow()
    application = Application(
        posting=posting,
        current_status=data.initial_status,
        status_changed_at=now,
        # Jeder Status außer "gemerkt" setzt voraus, dass die Bewerbung raus ist.
        applied_at=None if data.initial_status is ApplicationStatus.SAVED else now,
        priority=data.priority,
    )
    application.events.append(
        ApplicationStatusEvent(from_status=None, to_status=data.initial_status, occurred_at=now)
    )
    if with_listing and source is not JobSource.MANUAL:
        # Portal-Bezug auch als Listing festhalten, damit spätere Suchläufe die Stelle erkennen.
        posting.listings.append(
            Listing(
                source=source,
                external_id=external_id,
                url=data.url,
                url_normalized=url_normalized,
                title=data.title,
                company_name=data.company_name,
                location=data.location,
                remote_type=data.remote_type,
                employment_type=data.employment_type,
                salary_min=data.salary_min,
                salary_max=data.salary_max,
                salary_currency=data.salary_currency.upper(),
                description=data.description,
                posted_at=data.posted_at,
                first_seen_at=now,
                last_seen_at=now,
                raw_payload=data.raw_payload,
            )
        )
    session.add(posting)
    session.flush()
    if data.tags:
        add_tags(session, posting, data.tags)
    logger.info("Stelle %s angelegt (Quelle %s)", posting.id, source)
    return posting


def get_posting(session: Session, posting_id: int) -> JobPosting:
    posting = session.scalar(
        select(JobPosting)
        .where(JobPosting.id == posting_id)
        .options(
            selectinload(JobPosting.applications).selectinload(Application.events),
            selectinload(JobPosting.applications).selectinload(Application.notes),
            selectinload(JobPosting.tag_links),
        )
    )
    if posting is None:
        raise NotFoundError("Stelle", posting_id)
    return posting


def update_posting(
    session: Session, registry: SourceRegistry, posting_id: int, data: PostingUpdate
) -> JobPosting:
    posting = get_posting(session, posting_id)
    changes = data.model_dump(exclude_unset=True)

    if "tags" in changes:
        tags = changes.pop("tags")
        if tags is not None:
            set_tags(session, posting, tags)
            posting.updated_at = utcnow()

    if "company_name" in changes:
        name = changes.pop("company_name")
        posting.company = get_or_create_company(session, name) if name else None
    if "url" in changes:
        url = changes.pop("url")
        posting.url = url
        if url:
            ref = registry.identify(url)
            posting.url_normalized = ref.url_normalized
            posting.external_id = posting.external_id or ref.external_id
        else:
            posting.url_normalized = None
    if changes.get("title") is None:
        changes.pop("title", None)
    if changes.get("salary_currency"):
        changes["salary_currency"] = changes["salary_currency"].upper()

    for field, value in changes.items():
        setattr(posting, field, value)

    if (
        posting.salary_min is not None
        and posting.salary_max is not None
        and posting.salary_min > posting.salary_max
    ):
        raise ValueError("salary_min darf nicht größer als salary_max sein")

    session.flush()
    return posting


def set_archived(session: Session, posting_id: int, *, archived: bool) -> JobPosting:
    posting = get_posting(session, posting_id)
    posting.archived_at = utcnow() if archived else None
    session.flush()
    return posting


def _latest_application_join(stmt: Select[_RowT]) -> Select[_RowT]:
    latest_app_id = (
        select(func.max(Application.id))
        .where(Application.posting_id == JobPosting.id)
        .correlate(JobPosting)
        .scalar_subquery()
    )
    return stmt.outerjoin(Application, Application.id == latest_app_id).outerjoin(
        Company, Company.id == JobPosting.company_id
    )


def list_postings(session: Session, flt: PostingFilter) -> tuple[list[JobPosting], int]:
    """Filtern, Zählen und Sortieren laufen vollständig in der Datenbank."""
    where: list[ColumnElement[bool]] = []
    if not flt.include_archived:
        where.append(JobPosting.archived_at.is_(None))
    if flt.status:
        where.append(Application.current_status.in_(flt.status))
    if flt.source:
        where.append(JobPosting.source.in_(flt.source))
    if flt.remote:
        where.append(JobPosting.remote_type.in_(flt.remote))
    for key in {tag_key(t) for t in flt.tag}:
        where.append(
            exists().where(
                PostingTag.posting_id == JobPosting.id,
                PostingTag.removed_at.is_(None),
                PostingTag.tag_id == select(Tag.id).where(Tag.key == key).scalar_subquery(),
            )
        )
    if flt.location:
        where.append(func.lower(JobPosting.location).like(f"%{flt.location.lower()}%"))
    if flt.min_salary is not None:
        # Spanne überschneidet sich mit dem Wunsch: Maximum (oder Minimum) >= Wunschgehalt
        where.append(func.coalesce(JobPosting.salary_max, JobPosting.salary_min) >= flt.min_salary)
    if flt.follow_up_due:
        where.append(Application.follow_up_at <= utcnow())
    if flt.q:
        pattern = f"%{flt.q.lower()}%"
        where.append(
            or_(
                func.lower(JobPosting.title).like(pattern),
                func.lower(Company.name).like(pattern),
                func.lower(JobPosting.location).like(pattern),
                func.lower(JobPosting.description).like(pattern),
            )
        )

    base = _latest_application_join(select(JobPosting)).where(*where)
    count_stmt = _latest_application_join(select(func.count(JobPosting.id))).where(*where)
    total = session.scalar(count_stmt) or 0

    sort_col: SQLColumnExpression[Any] = {
        "created_at": JobPosting.created_at,
        "updated_at": JobPosting.updated_at,
        "status_changed_at": Application.status_changed_at,
        "priority": Application.priority,
        "title": func.lower(JobPosting.title),
    }[flt.sort]
    ordering = sort_col.desc() if flt.order == "desc" else sort_col.asc()

    rows = session.scalars(
        base.options(selectinload(JobPosting.applications), selectinload(JobPosting.tag_links))
        .order_by(ordering, JobPosting.id.desc())
        .limit(flt.limit)
        .offset(flt.offset)
    ).unique()
    return list(rows), total
