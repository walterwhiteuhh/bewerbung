from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from bewerbung.db.models import Company, JobPosting, Listing
from bewerbung.db.types import utcnow
from bewerbung.domain.errors import DomainError, NotFoundError
from bewerbung.domain.geo import place_from_payload
from bewerbung.domain.logos import clean_logo_url
from bewerbung.domain.matching import company_key, title_key
from bewerbung.domain.schemas import CompanyRead, CompanyUpdate
from bewerbung.domain.websites import normalize_website, website_from_payload
from bewerbung.sources.fetcher import FetchError
from bewerbung.sources.site_logo import LogoStore, SiteLogoFetcher

logger = logging.getLogger(__name__)

LOGO_FILES_PATH = "/api/logos/files/{name}"


def get_or_create_company(session: Session, name: str) -> Company:
    key = company_key(name)
    company = session.scalar(select(Company).where(Company.name_key == key))
    if company is None:
        company = Company(name=name.strip(), name_key=key)
        session.add(company)
        session.flush()
    return company


def derive_listing_keys(session: Session, listing: Listing) -> None:
    """Firma, Titel-Schlüssel und strukturierten Ort eines Listings setzen (idempotent)."""
    if listing.posting is not None and listing.posting.company_id is not None:
        listing.company_id = listing.posting.company_id
    elif listing.company_name and listing.company_name.strip():
        company = get_or_create_company(session, listing.company_name)
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
    for field, value in changes.items():
        setattr(company, field, value)
    session.flush()
    return company


async def fetch_logo_from_website(
    session: Session, store: LogoStore, fetcher: SiteLogoFetcher, company_id: int
) -> Company:
    company = get_company(session, company_id)
    if not company.website:
        raise DomainError("Für diese Firma ist keine Website hinterlegt")
    try:
        data = await fetcher.fetch_logo(company.website)
        stored = store.save(data)
    except (FetchError, ValueError) as exc:
        raise DomainError(f"Logo nicht gefunden: {exc}") from exc
    company.logo_url = LOGO_FILES_PATH.format(name=stored.name)
    company.logo_source = "website"
    company.logo_fetched_at = utcnow()
    session.flush()
    logger.info("Logo für Firma %s von %s geladen", company.id, company.website)
    return company
