"""Querbezüge und abgeleitete Merkmale für Anzeigen und gemerkte Stellen.

Alles wird zur Laufzeit aus den gespeicherten Daten berechnet (keine zweite Wahrheit):
gleiche Firma (``listings.company_id``), gleiche Stelle auf mehreren Portalen
(``company_id`` + ``title_key``), Entfernung zum Wohnort, Alter, Wiederveröffentlichung,
Profil-Passung und Ähnlichkeit zu gemerkten Stellen. Für eine Trefferliste werden die
Merkmale mit wenigen gebündelten Abfragen berechnet, nicht pro Anzeige.

``features_rows`` liefert dieselben Merkmale flach für den CSV-Export, damit ein späteres
Ranking-Modell exakt mit den Werten trainiert, die die Oberfläche zeigt.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from itertools import pairwise
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from bewerbung.db.models import (
    ApplicantProfile,
    Application,
    Company,
    JobPosting,
    Listing,
    SearchHit,
)
from bewerbung.db.types import utcnow
from bewerbung.domain.enums import ApplicationStatus, JobSource
from bewerbung.domain.geo import city_key, haversine_km, place_from_text
from bewerbung.domain.keywords import suggest_tags
from bewerbung.domain.matching import JobProfile, similarity, title_key
from bewerbung.domain.schemas import (
    CompanyActivity,
    JobFeatures,
    ListingBrief,
    PostingInsights,
    SimilarJob,
)
from bewerbung.services import letters, postings

ACTIVE_DAYS = 14
SIMILAR_MIN_SCORE = 0.25
SIMILAR_CANDIDATES = 400
# Keine Skills im engeren Sinn: Level, Arbeitsmodell, Arbeitszeit.
_NON_SKILLS = frozenset(
    {"junior", "senior", "lead", "werkstudent", "praktikum", "remote", "hybrid", "teilzeit"}
)
_APPLIED = {s for s in ApplicationStatus if s is not ApplicationStatus.SAVED}


# --- Kontext (einmal pro Anfrage) ------------------------------------------------


@dataclass(slots=True)
class Context:
    now: datetime
    home: tuple[float, float] | None
    max_distance_km: int | None
    skills: frozenset[str]
    city_centers: dict[str, tuple[float, float]]
    saved: list[tuple[JobPosting, JobProfile]] = field(default_factory=list)


def _city_centers(session: Session) -> dict[str, tuple[float, float]]:
    """Median-Koordinaten je Stadt aus allen Anzeigen mit Koordinaten."""
    rows = session.execute(
        select(Listing.city, Listing.lat, Listing.lon).where(
            Listing.lat.is_not(None), Listing.city.is_not(None)
        )
    ).all()
    points: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for city, lat, lon in rows:
        if (key := city_key(city)) and lat is not None and lon is not None:
            points[key].append((lat, lon))
    return {
        k: (statistics.median(p[0] for p in v), statistics.median(p[1] for p in v))
        for k, v in points.items()
    }


def locate_home(
    session: Session, profile: ApplicantProfile, centers: dict[str, tuple[float, float]] | None
) -> None:
    """Wohnort -> Koordinaten über PLZ oder Stadt bekannter Anzeigen (kein Geocoding-Dienst)."""
    if not profile.home_location:
        profile.home_lat = profile.home_lon = None
        return
    place = place_from_text(profile.home_location)
    if place.postal_code:
        row = session.execute(
            select(func.avg(Listing.lat), func.avg(Listing.lon)).where(
                Listing.postal_code == place.postal_code, Listing.lat.is_not(None)
            )
        ).one()
        if row[0] is not None:
            profile.home_lat, profile.home_lon = float(row[0]), float(row[1])
            return
    centers = centers if centers is not None else _city_centers(session)
    key = city_key(place.city)
    if key and key in centers:
        profile.home_lat, profile.home_lon = centers[key]


def _profile_skills(session: Session, profile: ApplicantProfile) -> frozenset[str]:
    skills = {s.casefold().lstrip("#") for s in profile.skills}
    cv = letters.cv_text_for(session, profile)
    if cv:
        skills |= {t.casefold() for t in suggest_tags(title="", description=cv)}
    return frozenset(skills - _NON_SKILLS)


def build_context(session: Session, *, with_saved: bool = True) -> Context:
    profile = letters.get_profile(session)
    centers = _city_centers(session)
    if profile.home_location and not profile.home_located:
        locate_home(session, profile, centers)
    ctx = Context(
        now=utcnow(),
        home=(profile.home_lat, profile.home_lon) if profile.home_located else None,  # type: ignore[arg-type]
        max_distance_km=profile.max_distance_km,
        skills=_profile_skills(session, profile),
        city_centers=centers,
    )
    if with_saved:
        saved = session.scalars(
            select(JobPosting)
            .where(JobPosting.archived_at.is_(None))
            .options(selectinload(JobPosting.tag_links))
        ).all()
        ctx.saved = [
            (p, JobProfile.build(p.title, p.description, p.tags, p.remote_type)) for p in saved
        ]
    return ctx


# --- Bausteine -------------------------------------------------------------------


def _job_skills(title: str, description: str | None) -> frozenset[str]:
    tags = suggest_tags(title=title, description=description)
    return frozenset(t.casefold() for t in tags) - _NON_SKILLS


def _match(
    ctx: Context, title: str, description: str | None
) -> tuple[float | None, list[str], list[str]]:
    job = _job_skills(title, description)
    if not job or not ctx.skills:
        return None, [], sorted(job)
    have = job & ctx.skills
    return round(len(have) / len(job), 2), sorted(have), sorted(job - ctx.skills)


def _position(
    ctx: Context, city: str | None, lat: float | None, lon: float | None
) -> tuple[tuple[float, float] | None, bool]:
    """Eigene Koordinaten, sonst Stadtmitte aus anderen Anzeigen (geschätzt)."""
    if lat is not None and lon is not None:
        return (lat, lon), False
    key = city_key(city)
    if key and key in ctx.city_centers:
        return ctx.city_centers[key], True
    return None, False


def _place_fields(
    ctx: Context, city: str | None, lat: float | None, lon: float | None
) -> dict[str, Any]:
    point, estimated = _position(ctx, city, lat, lon)
    distance = haversine_km(*ctx.home, *point) if ctx.home and point else None
    return {
        "city": city,
        "lat": point[0] if point else None,
        "lon": point[1] if point else None,
        "position_estimated": estimated,
        "distance_km": distance,
        "distance_estimated": estimated and distance is not None,
        "within_max_distance": (
            distance <= ctx.max_distance_km
            if distance is not None and ctx.max_distance_km
            else None
        ),
    }


def _company_activity(
    session: Session, company_ids: set[int], now: datetime
) -> dict[int, CompanyActivity]:
    if not company_ids:
        return {}
    active_since = now - timedelta(days=ACTIVE_DAYS)
    listing_rows = session.execute(
        select(Listing.company_id, Listing.source, Listing.last_seen_at).where(
            Listing.company_id.in_(company_ids)
        )
    ).all()
    stats: dict[int, dict[str, Any]] = {
        cid: {"listings": 0, "active": 0, "portals": set()} for cid in company_ids
    }
    for cid, source, last_seen in listing_rows:
        if cid is None:
            continue
        s = stats[cid]
        s["listings"] += 1
        s["active"] += last_seen >= active_since
        s["portals"].add(source)

    app_rows = session.execute(
        select(JobPosting.company_id, Application.current_status, Application.status_changed_at)
        .join(Application, Application.posting_id == JobPosting.id)
        .where(JobPosting.company_id.in_(company_ids))
        .order_by(Application.status_changed_at)
    ).all()
    saved: dict[int, int] = defaultdict(int)
    applied: dict[int, int] = defaultdict(int)
    rejected: dict[int, int] = defaultdict(int)
    last: dict[int, str] = {}
    for cid, status, _ in app_rows:
        if cid is None:
            continue
        saved[cid] += 1
        applied[cid] += status in _APPLIED
        rejected[cid] += status is ApplicationStatus.REJECTED
        last[cid] = status.value
    master = {c.id: c for c in session.scalars(select(Company).where(Company.id.in_(company_ids)))}
    return {
        cid: CompanyActivity(
            company_id=cid,
            listings=s["listings"],
            active_listings=s["active"],
            portals=sorted(s["portals"], key=str),
            website=master[cid].website if cid in master else None,
            social_links=(master[cid].social_links or {}) if cid in master else {},
            saved_postings=saved[cid],
            applications=applied[cid],
            rejections=rejected[cid],
            last_status=last.get(cid),
        )
        for cid, s in stats.items()
    }


def _siblings(
    session: Session, listings: Sequence[Listing]
) -> dict[tuple[int, str], list[Listing]]:
    """Alle Listings mit gleicher Firma + gleichem Titel-Schlüssel (= dieselbe Stelle)."""
    pairs = {
        (lst.company_id, lst.title_key) for lst in listings if lst.company_id and lst.title_key
    }
    if not pairs:
        return {}
    rows = session.scalars(
        select(Listing).where(
            Listing.company_id.in_({c for c, _ in pairs}),
            Listing.title_key.in_({t for _, t in pairs}),
        )
    ).all()
    groups: dict[tuple[int, str], list[Listing]] = defaultdict(list)
    for row in rows:
        if row.company_id is not None and row.title_key is not None:
            key = (row.company_id, row.title_key)
            if key in pairs:
                groups[key].append(row)
    return groups


def _is_repost(group: list[Listing]) -> bool:
    """Dieselbe Stelle unter neuer ID im selben Portal, nachdem die alte verschwand."""
    by_source: dict[JobSource, list[Listing]] = defaultdict(list)
    for item in group:
        by_source[item.source].append(item)
    for items in by_source.values():
        items.sort(key=lambda x: x.first_seen_at)
        if any(b.first_seen_at > a.last_seen_at for a, b in pairwise(items)):
            return True
        if len({i.external_id for i in items}) > 1 and len(items) > 1:
            return True
    return False


def _best_similar(
    ctx: Context, profile: JobProfile, exclude_posting: int | None
) -> SimilarJob | None:
    best: SimilarJob | None = None
    for posting, other in ctx.saved:
        if posting.id == exclude_posting:
            continue
        sim = similarity(profile, other)
        if sim.score >= SIMILAR_MIN_SCORE and (best is None or sim.score > best.score):
            best = SimilarJob(
                kind="posting",
                id=posting.id,
                title=posting.title,
                company_name=posting.company.name if posting.company else None,
                score=sim.score,
                shared=[*sim.shared_skills, *sim.shared_title][:6],
            )
    return best


# --- Öffentliche Funktionen ------------------------------------------------------


def listing_features(
    session: Session, listings: Sequence[Listing], ctx: Context | None = None
) -> dict[int, JobFeatures]:
    """Merkmale für viele Listings auf einmal (z. B. alle Treffer eines Suchlaufs)."""
    if not listings:
        return {}
    ctx = ctx or build_context(session)
    ids = [lst.id for lst in listings]
    seen_counts = dict(
        session.execute(
            select(SearchHit.listing_id, func.count())
            .where(SearchHit.listing_id.in_(ids))
            .group_by(SearchHit.listing_id)
        ).all()
    )
    companies = _company_activity(
        session, {lst.company_id for lst in listings if lst.company_id}, ctx.now
    )
    siblings = _siblings(session, listings)

    out: dict[int, JobFeatures] = {}
    for lst in listings:
        group = siblings.get((lst.company_id, lst.title_key), [lst])  # type: ignore[arg-type]
        score, have, missing = _match(ctx, lst.title, lst.description)
        reference = lst.posted_at or lst.first_seen_at
        out[lst.id] = JobFeatures(
            **_place_fields(ctx, lst.city, lst.lat, lst.lon),
            postal_code=lst.postal_code,
            region=lst.region,
            age_days=max((ctx.now - reference).days, 0) if reference else None,
            days_online=(lst.last_seen_at - lst.first_seen_at).days,
            times_seen=int(seen_counts.get(lst.id, 0)),
            portals=sorted({g.source for g in group}, key=str),
            is_repost=_is_repost(group),
            match_score=score,
            matched_skills=have,
            missing_skills=missing[:8],
            company=companies.get(lst.company_id) if lst.company_id else None,
            similar_saved=_best_similar(
                ctx,
                JobProfile.build(lst.title, lst.description, (), lst.remote_type),
                lst.posting_id,
            ),
        )
    return out


def _brief(lst: Listing) -> ListingBrief:
    return ListingBrief.model_validate(lst)


def posting_insights(session: Session, posting_id: int) -> PostingInsights:
    posting = postings.get_posting(session, posting_id)
    ctx = build_context(session)
    own = sorted(posting.listings, key=lambda x: x.last_seen_at, reverse=True)

    if own:
        features = listing_features(session, own[:1], ctx)[own[0].id]
    else:  # manuell erfasst: Merkmale aus der Stelle selbst
        place = place_from_text(posting.location)
        score, have, missing = _match(ctx, posting.title, posting.description)
        companies = _company_activity(
            session, {posting.company_id} if posting.company_id else set(), ctx.now
        )
        features = JobFeatures(
            **_place_fields(ctx, place.city, None, None),
            postal_code=place.postal_code,
            age_days=(ctx.now - (posting.posted_at or posting.created_at)).days,
            match_score=score,
            matched_skills=have,
            missing_skills=missing[:8],
            company=companies.get(posting.company_id) if posting.company_id else None,
        )
    features.similar_saved = None  # in der Stelle selbst nicht sinnvoll

    # Dieselbe Stelle auf anderen Portalen (gleiche Firma + gleicher Titel).
    key = title_key(posting.title)
    other_portals: list[ListingBrief] = []
    if posting.company_id:
        rows = session.scalars(
            select(Listing).where(
                Listing.company_id == posting.company_id,
                Listing.title_key == key,
            )
        ).all()
        own_ids = {o.id for o in own}
        other_portals = [_brief(r) for r in rows if r.id not in own_ids]

    same_company_postings: list[SimilarJob] = []
    same_company_listings: list[ListingBrief] = []
    if posting.company_id:
        for other, _ in ctx.saved:
            if other.company_id == posting.company_id and other.id != posting.id:
                status = other.application.current_status.value if other.application else None
                same_company_postings.append(
                    SimilarJob(
                        kind="posting",
                        id=other.id,
                        title=other.title,
                        company_name=posting.company.name if posting.company else None,
                        score=1.0,
                        shared=[status] if status else [],
                    )
                )
        active_since = ctx.now - timedelta(days=60)
        rows = session.scalars(
            select(Listing)
            .where(
                Listing.company_id == posting.company_id,
                Listing.posting_id.is_(None),
                Listing.title_key != key,
                Listing.last_seen_at >= active_since,
            )
            .order_by(Listing.last_seen_at.desc())
            .limit(8)
        ).all()
        same_company_listings = [_brief(r) for r in rows]

    me = JobProfile.build(posting.title, posting.description, posting.tags, posting.remote_type)
    similar: list[SimilarJob] = []
    for other, prof in ctx.saved:
        if other.id == posting.id:
            continue
        sim = similarity(me, prof)
        if sim.score >= SIMILAR_MIN_SCORE:
            similar.append(
                SimilarJob(
                    kind="posting",
                    id=other.id,
                    title=other.title,
                    company_name=other.company.name if other.company else None,
                    score=sim.score,
                    shared=[*sim.shared_skills, *sim.shared_title][:6],
                )
            )
    candidates = session.scalars(
        select(Listing)
        .where(Listing.posting_id.is_(None))
        .order_by(Listing.last_seen_at.desc())
        .limit(SIMILAR_CANDIDATES)
    ).all()
    for cand in candidates:
        sim = similarity(me, JobProfile.build(cand.title, cand.description, (), cand.remote_type))
        if sim.score >= SIMILAR_MIN_SCORE:
            similar.append(
                SimilarJob(
                    kind="listing",
                    id=cand.id,
                    title=cand.title,
                    company_name=cand.company_name,
                    score=sim.score,
                    shared=[*sim.shared_skills, *sim.shared_title][:6],
                )
            )
    similar.sort(key=lambda s: -s.score)
    return PostingInsights(
        features=features,
        other_portals=other_portals,
        same_company_postings=same_company_postings,
        same_company_listings=same_company_listings,
        similar=similar[:8],
    )


EXPORT_COLUMNS = (
    "listing_id",
    "posting_id",
    "source",
    "company_id",
    "company_name",
    "title",
    "title_key",
    "remote_type",
    "employment_type",
    "salary_min",
    "salary_max",
    "first_seen_at",
    "last_seen_at",
    "posted_at",
    "label_status",
)


def features_rows(session: Session, batch: int = 500) -> Iterator[dict[str, Any]]:
    """Alle Listings mit Merkmalen, flach; ``label_status`` = späteres Trainingslabel."""
    ctx = build_context(session)
    status_by_posting = dict(
        session.execute(select(Application.posting_id, Application.current_status)).all()
    )
    last_id = 0
    while True:
        chunk = session.scalars(
            select(Listing).where(Listing.id > last_id).order_by(Listing.id).limit(batch)
        ).all()
        if not chunk:
            return
        feats = listing_features(session, chunk, ctx)
        for lst in chunk:
            f = feats[lst.id]
            status = status_by_posting.get(lst.posting_id) if lst.posting_id else None
            company = f.company
            yield {
                "listing_id": lst.id,
                "posting_id": lst.posting_id,
                "source": lst.source.value,
                "company_id": lst.company_id,
                "company_name": lst.company_name,
                "title": lst.title,
                "title_key": lst.title_key,
                "remote_type": lst.remote_type.value,
                "employment_type": lst.employment_type,
                "salary_min": lst.salary_min,
                "salary_max": lst.salary_max,
                "first_seen_at": lst.first_seen_at.isoformat(),
                "last_seen_at": lst.last_seen_at.isoformat(),
                "posted_at": lst.posted_at.isoformat() if lst.posted_at else None,
                "label_status": status.value if status else None,
                "city": f.city,
                "region": f.region,
                "distance_km": f.distance_km,
                "distance_estimated": f.distance_estimated,
                "age_days": f.age_days,
                "days_online": f.days_online,
                "times_seen": f.times_seen,
                "portal_count": len(f.portals),
                "is_repost": f.is_repost,
                "match_score": f.match_score,
                "matched_skills": " ".join(f.matched_skills),
                "missing_skills": " ".join(f.missing_skills),
                "company_listings": company.listings if company else None,
                "company_active_listings": company.active_listings if company else None,
                "company_applications": company.applications if company else None,
                "company_rejections": company.rejections if company else None,
                "similar_saved_score": f.similar_saved.score if f.similar_saved else None,
            }
        last_id = chunk[-1].id
