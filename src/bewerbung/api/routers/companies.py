"""Firmen, Logos und Arbeitgeber-Bewertungen."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse

from bewerbung.api.deps import LogoStoreDep, SessionDep, SiteLogosDep
from bewerbung.domain.schemas import (
    CompanyRatingCreate,
    CompanyRatingRead,
    CompanyRead,
    CompanyUpdate,
)
from bewerbung.services import companies
from bewerbung.sources.site_logo import MEDIA_TYPES

router = APIRouter()


@router.get("/logos/files/{name}", tags=["companies"], include_in_schema=False)
def logo_file(store: LogoStoreDep, name: str) -> FileResponse:
    """Lokal abgelegtes Firmenlogo (von der Firmen-Website geladen)."""
    path = store.path(name)
    if path is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kein Logo")
    ext = name.rsplit(".", 1)[-1]
    return FileResponse(
        path,
        media_type=MEDIA_TYPES[ext],
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",  # Name = Inhalts-Hash
            "X-Content-Type-Options": "nosniff",
            # SVG darf beim direkten Öffnen keine Skripte ausführen.
            "Content-Security-Policy": "default-src 'none'; style-src 'unsafe-inline'; sandbox",
        },
    )


@router.get("/companies", response_model=list[CompanyRead], tags=["companies"])
def list_companies(session: SessionDep) -> list[CompanyRead]:
    return [companies.to_read(c, n) for c, n in companies.list_companies(session)]


@router.get("/companies/{company_id}", response_model=CompanyRead, tags=["companies"])
def get_company(session: SessionDep, company_id: int) -> CompanyRead:
    return companies.to_read(companies.get_company(session, company_id))


@router.patch("/companies/{company_id}", response_model=CompanyRead, tags=["companies"])
def update_company(session: SessionDep, company_id: int, data: CompanyUpdate) -> CompanyRead:
    return companies.to_read(companies.update_company(session, company_id, data))


@router.post("/companies/{company_id}/logo", response_model=CompanyRead, tags=["companies"])
async def fetch_company_logo(
    session: SessionDep, store: LogoStoreDep, fetcher: SiteLogosDep, company_id: int
) -> CompanyRead:
    """Logo von der hinterlegten Firmen-Website laden (ersetzt das bisherige Logo)."""
    company = await companies.fetch_logo_from_website(session, store, fetcher, company_id)
    return companies.to_read(company)


@router.post(
    "/companies/{company_id}/ratings",
    response_model=CompanyRead,
    status_code=status.HTTP_201_CREATED,
    tags=["companies"],
)
def add_company_rating(
    session: SessionDep, company_id: int, data: CompanyRatingCreate
) -> CompanyRead:
    """Arbeitgeber-Bewertung eines Portals erfassen (Wert, Skala, Anzahl Bewertungen)."""
    return companies.to_read(companies.add_rating(session, company_id, data))


@router.get(
    "/companies/{company_id}/ratings",
    response_model=list[CompanyRatingRead],
    tags=["companies"],
)
def list_company_ratings(session: SessionDep, company_id: int) -> list[CompanyRatingRead]:
    """Vollständiger Verlauf aller erfassten Bewertungen, älteste zuerst."""
    company = companies.get_company(session, company_id)
    return [CompanyRatingRead.model_validate(r) for r in company.ratings]


@router.delete(
    "/companies/{company_id}/ratings/{rating_id}", response_model=CompanyRead, tags=["companies"]
)
def delete_company_rating(session: SessionDep, company_id: int, rating_id: int) -> CompanyRead:
    return companies.to_read(companies.delete_rating(session, company_id, rating_id))
