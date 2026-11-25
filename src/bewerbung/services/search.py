"""Live-Suche: Provider parallel abfragen, Treffer als Listings upserten, Lauf protokollieren."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence
from datetime import datetime
from itertools import chain, zip_longest

from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from bewerbung.db.models import JobPosting, Listing, SearchHit, SearchProfile, SearchRun
from bewerbung.db.types import utcnow
from bewerbung.domain.errors import DuplicatePostingError, NotFoundError
from bewerbung.domain.keywords import suggest_tags
from bewerbung.domain.schemas import (
    PostingCreate,
    ProviderInfo,
    SaveListing,
    SearchProfileCreate,
    SearchRequest,
)
from bewerbung.search.base import ListingDraft, SearchProvider, SearchQuery
from bewerbung.services import postings
from bewerbung.services.tags import add_tags
from bewerbung.sources import SourceRegistry

logger = logging.getLogger(__name__)


def provider_infos(providers: Sequence[SearchProvider]) -> list[ProviderInfo]:
    return [
        ProviderInfo(
            source=p.source,
            label=p.label,
            available=p.unavailable_reason is None,
            reason=p.unavailable_reason,
        )
        for p in providers
    ]


def _normalized_url(registry: SourceRegistry, url: str | None) -> str | None:
    if not url:
        return None
    try:
        return registry.identify(url).url_normalized
    except ValueError:
        return None


def upsert_listing(
    session: Session, registry: SourceRegistry, draft: ListingDraft, now: datetime
) -> tuple[Listing, bool]:
    """Neue Anzeige anlegen oder bestehende aktualisieren. Gibt (listing, ist_neu) zurück."""
    listing = session.scalar(
        select(Listing).where(
            Listing.source == draft.source, Listing.external_id == draft.external_id
        )
    )
    fields = draft.model_dump(exclude={"raw", "source", "external_id"})
    content_hash = draft.content_hash()

    if listing is None:
        # Schon manuell gemerkt? Dann direkt mit der Stelle verknüpfen.
        posting_id = session.scalar(
            select(JobPosting.id).where(
                JobPosting.source == draft.source, JobPosting.external_id == draft.external_id
            )
        )
        listing = Listing(
            source=draft.source,
            external_id=draft.external_id,
            url_normalized=_normalized_url(registry, draft.url),
            posting_id=posting_id,
            first_seen_at=now,
            last_seen_at=now,
            content_hash=content_hash,
            raw_payload=draft.raw,
            **fields,
        )
        session.add(listing)
        return listing, True

    if listing.content_hash != content_hash:
        for key, value in fields.items():
            # Fehlt ein Feld in diesem Lauf (z. B. ungefilterte Suche ohne Arbeitszeit),
            # ist das keine Löschung: bekannte Werte bleiben stehen.
            if value is not None:
                setattr(listing, key, value)
        listing.content_hash = content_hash
        listing.raw_payload = draft.raw
    if draft.company_logo_url and listing.company_logo_url != draft.company_logo_url:
        listing.company_logo_url = draft.company_logo_url  # nicht Teil des Inhalts-Hashs
    listing.last_seen_at = now
    listing.expired_at = None
    return listing, False


def _interleave(results: list[list[ListingDraft]]) -> list[ListingDraft]:
    """Abwechselnd aus jeder Quelle, damit keine Quelle die ersten Ränge dominiert."""
    return [d for d in chain.from_iterable(zip_longest(*results)) if d is not None]


async def run_search(
    session: Session,
    registry: SourceRegistry,
    providers: Sequence[SearchProvider],
    req: SearchRequest,
) -> SearchRun:
    wanted = [p for p in providers if not req.sources or p.source in req.sources]
    usable = [p for p in wanted if p.unavailable_reason is None]
    # Fehlende Keys nur melden, wenn die Quelle ausdrücklich gewählt wurde.
    errors = [
        {"source": p.source.value, "message": p.unavailable_reason or ""}
        for p in wanted
        if p.unavailable_reason is not None and req.sources
    ]

    query = SearchQuery(
        query=req.query,
        location=req.location,
        radius_km=req.radius_km,
        remote_only=req.remote_only,
        work_times=req.work_times,
        offer_type=req.offer_type,
    )
    run = SearchRun(
        profile_id=req.profile_id,
        query=req.query,
        location=req.location,
        radius_km=req.radius_km,
        remote_only=req.remote_only,
        work_times=list(req.work_times),
        offer_type=req.offer_type,
        sources=[p.source.value for p in wanted],
        started_at=utcnow(),
    )

    outcomes = await asyncio.gather(*(p.search(query) for p in usable), return_exceptions=True)
    results: list[list[ListingDraft]] = []
    for provider, outcome in zip(usable, outcomes, strict=True):
        if isinstance(outcome, BaseException):
            logger.warning("Suche bei %s fehlgeschlagen: %s", provider.source, outcome)
            errors.append({"source": provider.source.value, "message": str(outcome)})
        else:
            results.append(outcome)

    now = utcnow()
    seen: set[int] = set()
    for draft in _interleave(results):
        listing, is_new = upsert_listing(session, registry, draft, now)
        session.flush()
        if listing.id in seen:
            continue
        seen.add(listing.id)
        run.hits.append(SearchHit(listing=listing, rank=len(run.hits) + 1, is_new=is_new))

    run.total_hits = len(run.hits)
    run.new_hits = sum(h.is_new for h in run.hits)
    run.errors = errors
    run.finished_at = utcnow()
    session.add(run)
    session.flush()
    logger.info("Suchlauf %s: %d Treffer (%d neu)", run.id, run.total_hits, run.new_hits)
    return run


def get_run(session: Session, run_id: int) -> SearchRun:
    run = session.scalar(
        select(SearchRun).where(SearchRun.id == run_id).options(selectinload(SearchRun.hits))
    )
    if run is None:
        raise NotFoundError("Suchlauf", run_id)
    return run


def list_runs(session: Session, limit: int = 20) -> list[SearchRun]:
    stmt = (
        select(SearchRun)
        .where(SearchRun.hidden_at.is_(None))
        .order_by(SearchRun.id.desc())
        .limit(limit)
    )
    return list(session.scalars(stmt))


def hide_run(session: Session, run_id: int) -> None:
    run = session.get(SearchRun, run_id)
    if run is None:
        raise NotFoundError("Suchlauf", run_id)
    run.hidden_at = run.hidden_at or utcnow()
    session.flush()


def hide_all_runs(session: Session) -> int:
    result = session.execute(
        update(SearchRun).where(SearchRun.hidden_at.is_(None)).values(hidden_at=utcnow())
    )
    return int(getattr(result, "rowcount", 0) or 0)


def get_listing(session: Session, listing_id: int) -> Listing:
    listing = session.get(Listing, listing_id)
    if listing is None:
        raise NotFoundError("Anzeige", listing_id)
    return listing


def save_listing(
    session: Session, registry: SourceRegistry, listing_id: int, data: SaveListing
) -> JobPosting:
    """Treffer merken: Stelle + Bewerbung anlegen (idempotent) und verknüpfen."""
    listing = get_listing(session, listing_id)
    if listing.posting_id is not None:
        return postings.get_posting(session, listing.posting_id)

    create = PostingCreate(
        title=listing.title,
        company_name=listing.company_name,
        company_logo_url=listing.company_logo_url,
        location=listing.location,
        remote_type=listing.remote_type,
        employment_type=listing.employment_type,
        salary_min=listing.salary_min,
        salary_max=listing.salary_max,
        salary_currency=listing.salary_currency or "EUR",
        description=listing.description,
        posted_at=listing.posted_at,
        url=listing.url,
        source=listing.source,
        external_id=listing.external_id,
        raw_payload={"listing_id": listing.id, "source_payload": listing.raw_payload},
        initial_status=data.initial_status,
        priority=data.priority,
    )
    try:
        posting = postings.create_posting(session, registry, create, with_listing=False)
    except DuplicatePostingError as dup:
        posting = postings.get_posting(session, dup.existing_id)
    else:
        auto = suggest_tags(
            title=listing.title,
            description=listing.description,
            location=listing.location,
            remote_type=listing.remote_type,
            employment_type=listing.employment_type,
        )
        if auto:
            add_tags(session, posting, auto, origin="auto")
    listing.posting_id = posting.id
    session.flush()
    return postings.get_posting(session, posting.id)


# --- Profile ---------------------------------------------------------------------


def create_profile(session: Session, data: SearchProfileCreate) -> SearchProfile:
    profile = SearchProfile(**data.model_dump(mode="json"))
    session.add(profile)
    session.flush()
    return profile


def list_profiles(session: Session) -> list[SearchProfile]:
    return list(
        session.scalars(
            select(SearchProfile)
            .where(SearchProfile.archived_at.is_(None))
            .order_by(SearchProfile.name)
        )
    )


def _active_profile(session: Session, profile_id: int) -> SearchProfile:
    profile = session.get(SearchProfile, profile_id)
    if profile is None or profile.archived_at is not None:
        raise NotFoundError("Suchprofil", profile_id)
    return profile


def update_profile(session: Session, profile_id: int, data: SearchProfileCreate) -> SearchProfile:
    """Gespeicherte Suche ändern. Frühere Läufe behalten ihre eigenen Parameter (Snapshot)."""
    profile = _active_profile(session, profile_id)
    for key, value in data.model_dump(mode="json").items():
        setattr(profile, key, value)
    session.flush()
    return profile


def archive_profile(session: Session, profile_id: int) -> None:
    profile = _active_profile(session, profile_id)
    profile.archived_at = utcnow()
    session.flush()
