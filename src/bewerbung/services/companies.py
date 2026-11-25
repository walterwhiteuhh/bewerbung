from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bewerbung.db.models import Company, CompanyRating, JobPosting, Listing
from bewerbung.db.types import utcnow
from bewerbung.domain.errors import DomainError, NotFoundError
from bewerbung.domain.geo import place_from_payload
from bewerbung.domain.logos import clean_logo_url
from bewerbung.domain.matching import company_key, title_key
from bewerbung.domain.ratings import normalize
from bewerbung.domain.schemas import CompanyRatingCreate, CompanyRead, CompanyUpdate
from bewerbung.domain.socials import (
    classify_social,
    merge_socials,
    order_socials,
    socials_from_payload,
)
from bewerbung.domain.websites import normalize_website, website_from_payload
from bewerbung.sources.site_logo import LogoStore, SiteLogoFetcher

logger = logging.getLogger(__name__)

LOGO_FILES_PATH = "/api/logos/files/{name}"


def get_or_create_company(
    session: Session, name: str, cache: dict[str, Company] | None = None
) -> Company:
    """Firma über den normalisierten Namen finden oder anlegen.

    Mit ``cache`` (name_key -> Firma, z. B. für einen ganzen Suchlauf) entfällt die
    Einzelabfrage je Anzeige.
    """
    key = company_key(name)
    company = cache.get(key) if cache is not None else None
    if company is None:
        company = session.scalar(select(Company).where(Company.name_key == key))
    if company is None:
        company = Company(name=name.strip(), name_key=key)
        session.add(company)
        session.flush()
    if cache is not None:
        cache[key] = company
    return company


def derive_listing_keys(
    session: Session, listing: Listing, cache: dict[str, Company] | None = None
) -> None:
    """Firma, Titel-Schlüssel und strukturierten Ort eines Listings setzen (idempotent)."""
    if listing.posting is not None and listing.posting.company_id is not None:
        listing.company_id = listing.posting.company_id
    elif listing.company_name and listing.company_name.strip():
        company = get_or_create_company(session, listing.company_name, cache)
        enrich_from_posting(company, listing.company_logo_url, listing.raw_payload)
        listing.company_id = company.id
    listing.title_key = title_key(listing.title or "")
    place = place_from_payload(listing.raw_payload, listing.location)
    listing.city = place.city[:120] if place.city else None
    listing.postal_code = place.postal_code[:10] if place.postal_code else None
    listing.region = place.region[:120] if place.region else None
    listing.lat, listing.lon = place.lat, place.lon


def enrich_from_posting(company: Company, logo_url: str | None, raw_payload: Any) -> None:
    """Leere Stammdaten aus einer neuen Anzeige ergänzen; vorhandene Werte bleiben."""
    if logo_url and not company.logo_url:
        company.logo_url = logo_url
        company.logo_source = "portal"
    if not company.website and (site := website_from_payload(raw_payload)):
        company.website = site
    if socials := socials_from_payload(raw_payload):
        merged = merge_socials(company.social_links, socials)
        if merged != (company.social_links or {}):
            company.social_links = merged


def get_company(session: Session, company_id: int) -> Company:
    company = session.get(Company, company_id)
    if company is None:
        raise NotFoundError("Firma", company_id)
    return company


def list_companies(session: Session) -> list[tuple[Company, int]]:
    """Firmen mit Anzahl der (nicht archivierten) Stellen, häufigste zuerst."""
    count = func.count(JobPosting.id).filter(JobPosting.archived_at.is_(None))
    stmt = (
        select(Company, count)
        .outerjoin(JobPosting, JobPosting.company_id == Company.id)
        .group_by(Company.id)
        .order_by(count.desc(), Company.name)
    )
    return [(c, int(n)) for c, n in session.execute(stmt).all()]


def to_read(company: Company, posting_count: int | None = None) -> CompanyRead:
    read = CompanyRead.model_validate(company)
    return read.model_copy(update={"posting_count": posting_count})


def update_company(session: Session, company_id: int, data: CompanyUpdate) -> Company:
    company = get_company(session, company_id)
    changes = data.model_dump(exclude_unset=True)
    if "website" in changes:
        raw = changes.pop("website")
        website = normalize_website(raw)
        if raw and website is None:
            raise DomainError("Bitte eine gültige Website angeben, z. B. firma.de")
        company.website = website
    if "name" in changes:
        name = (changes.pop("name") or "").strip()
        if name and name != company.name:
            key = company_key(name)
            other = session.scalar(select(Company.id).where(Company.name_key == key))
            if other is not None and other != company.id:
                raise DomainError(f"Eine Firma namens „{name}“ gibt es schon")
            company.name, company.name_key = name, key
    if "logo_url" in changes:
        raw_logo = changes.pop("logo_url")
        logo = clean_logo_url(raw_logo)
        if raw_logo and logo is None:
            raise DomainError("Logo-Adresse muss mit https:// beginnen")
        company.logo_url = logo
        company.logo_source = "manual" if company.logo_url else None
    if "social_links" in changes:
        company.social_links = _manual_socials(changes.pop("social_links") or []) or None
    for field, value in changes.items():
        setattr(company, field, value)
    session.flush()
    return company


def _manual_socials(urls: list[str]) -> dict[str, str]:
    links: dict[str, str] = {}
    for url in filter(None, (u.strip() for u in urls)):
        hit = classify_social(url)
        if hit is None:
            raise DomainError(
                f"„{url}“ ist kein erkanntes Profil (LinkedIn, XING, kununu, Instagram, "
                "Facebook, YouTube, X, TikTok, GitHub)"
            )
        links[hit[0]] = hit[1]
    return order_socials(links)


async def fetch_logo_from_website(
    session: Session, store: LogoStore, fetcher: SiteLogoFetcher, company_id: int
) -> Company:
    """Logo und Social-Media-Profile von der Firmen-Website übernehmen."""
    company = get_company(session, company_id)
    if not company.website:
        raise DomainError("Für diese Firma ist keine Website hinterlegt")
    site = await fetcher.fetch_site(company.website)
    if site.socials:
        company.social_links = merge_socials(company.social_links, site.socials)
    if site.logo is None:
        if not site.socials:
            raise DomainError("Logo nicht gefunden: Auf der Website wurde kein Logo gefunden")
        session.flush()
        return company
    try:
        stored = store.save(site.logo)
    except ValueError as exc:
        raise DomainError(f"Logo nicht gefunden: {exc}") from exc
    company.logo_url = LOGO_FILES_PATH.format(name=stored.name)
    company.logo_source = "website"
    company.logo_fetched_at = utcnow()
    session.flush()
    logger.info("Website von Firma %s ausgewertet: Logo, %d Profile", company.id, len(site.socials))
    return company


# --- Arbeitgeber-Bewertungen ------------------------------------------------------


def add_rating(session: Session, company_id: int, data: CompanyRatingCreate) -> Company:
    """Neuen Stand eines Portals erfassen; frühere Werte bleiben als Verlauf erhalten."""
    company = get_company(session, company_id)
    url = normalize_website(data.url) if data.url else None
    if data.url and url is None:
        raise DomainError("Bitte einen gültigen Link zur Bewertungsseite angeben")
    rating = CompanyRating(
        source=data.source.value,
        rating=normalize(data.value, data.scale_max),
        raw_value=data.value,
        scale_max=data.scale_max,
        review_count=data.review_count,
        url=url,
        method="manual",
    )
    company.ratings.append(rating)
    session.flush()
    session.refresh(company, ["ratings"])
    return company


def delete_rating(session: Session, company_id: int, rating_id: int) -> Company:
    """Fehleingabe entfernen (nur dieser Eintrag; der vorige Stand gilt dann wieder)."""
    company = get_company(session, company_id)
    rating = session.get(CompanyRating, rating_id)
    if rating is None or rating.company_id != company.id:
        raise NotFoundError("Bewertung", rating_id)
    session.delete(rating)
    session.flush()
    session.refresh(company, ["ratings"])
    return company
