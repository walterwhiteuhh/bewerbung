"""Portalsuche, Suchläufe, gespeicherte Suchen und Treffer."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from bewerbung.api.deps import AaLogosDep, ProvidersDep, RegistryDep, SessionDep
from bewerbung.domain.keywords import suggest_tags
from bewerbung.domain.schemas import (
    ListingRead,
    PostingDetail,
    ProviderInfo,
    SaveListing,
    SearchProfileCreate,
    SearchProfileRead,
    SearchRequest,
    SearchRunRead,
    SearchRunSummary,
)
from bewerbung.services import insights, search

router = APIRouter()


@router.get("/logos/arbeitsagentur/{logo_hash}", tags=["search"], include_in_schema=False)
async def arbeitsagentur_logo(cache: AaLogosDep, logo_hash: str) -> FileResponse:
    """Arbeitgeberlogo der Arbeitsagentur (einmal geladen, dann lokal aus dem Cache)."""
    logo = await cache.get(logo_hash)
    if logo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kein Logo")
    return FileResponse(
        logo.path,
        media_type=logo.media_type,
        headers={"Cache-Control": "public, max-age=604800", "X-Content-Type-Options": "nosniff"},
    )


@router.get("/search/providers", response_model=list[ProviderInfo], tags=["search"])
def search_providers(providers: ProvidersDep) -> list[ProviderInfo]:
    return search.provider_infos(providers)


@router.post("/search", response_model=SearchRunRead, tags=["search"])
async def run_search(
    session: SessionDep, registry: RegistryDep, providers: ProvidersDep, data: SearchRequest
) -> SearchRunRead:
    """Gewählte Portale parallel durchsuchen; Fehler einzelner Portale stehen in ``errors``."""
    run = await search.run_search(session, registry, providers, data)
    return _run_with_features(session, run)


@router.get("/search/runs", response_model=list[SearchRunSummary], tags=["search"])
def list_runs(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 20,
    started_from: Annotated[datetime | None, Query(alias="from")] = None,
    started_to: Annotated[datetime | None, Query(alias="to")] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
) -> list[SearchRunSummary]:
    """Verlauf; ``from`` (inklusive) und ``to`` (exklusiv) grenzen den Zeitraum ein."""
    runs = search.list_runs(
        session, limit, started_from=started_from, started_to=started_to, text=q
    )
    return [SearchRunSummary.model_validate(r) for r in runs]


@router.delete("/search/runs", tags=["search"])
def clear_runs(
    session: SessionDep,
    ids: Annotated[list[int] | None, Query()] = None,
    started_from: Annotated[datetime | None, Query(alias="from")] = None,
    started_to: Annotated[datetime | None, Query(alias="to")] = None,
) -> dict[str, int]:
    """Verlauf leeren, komplett oder nur Teile (``ids`` und/oder Zeitraum).

    Läufe werden ausgeblendet, nicht gelöscht (Auswertung bleibt möglich)."""
    return {
        "hidden": search.hide_runs(
            session, ids=ids, started_from=started_from, started_to=started_to
        )
    }


@router.delete("/search/runs/{run_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["search"])
def delete_run(session: SessionDep, run_id: int) -> None:
    search.hide_run(session, run_id)


@router.get("/search/runs/{run_id}", response_model=SearchRunRead, tags=["search"])
def get_run(session: SessionDep, run_id: int) -> SearchRunRead:
    return _run_with_features(session, search.get_run(session, run_id))


def _run_with_features(session: SessionDep, run: Any) -> SearchRunRead:
    read = SearchRunRead.model_validate(run)
    feats = insights.listing_features(session, [h.listing for h in run.hits])
    for hit, src in zip(read.hits, run.hits, strict=True):
        hit.features = feats.get(hit.listing.id)
        hit.tags = _hit_tags(src.listing)
    return read


def _hit_tags(listing: Any) -> list[str]:
    """Gemerkt: die echten Hashtags der Stelle. Sonst Vorschläge aus Titel und Beschreibung."""
    if listing.posting is not None and listing.posting.tags:
        return list(listing.posting.tags)
    return suggest_tags(
        title=listing.title,
        description=listing.description,
        location=listing.location,
        remote_type=listing.remote_type,
        employment_type=listing.employment_type,
    )


@router.get("/search/profiles", response_model=list[SearchProfileRead], tags=["search"])
def list_profiles(session: SessionDep) -> list[SearchProfileRead]:
    return [SearchProfileRead.model_validate(p) for p in search.list_profiles(session)]


@router.post(
    "/search/profiles",
    response_model=SearchProfileRead,
    status_code=status.HTTP_201_CREATED,
    tags=["search"],
)
def create_profile(session: SessionDep, data: SearchProfileCreate) -> SearchProfileRead:
    return SearchProfileRead.model_validate(search.create_profile(session, data))


@router.put("/search/profiles/{profile_id}", response_model=SearchProfileRead, tags=["search"])
def put_search_profile(
    session: SessionDep, profile_id: int, data: SearchProfileCreate
) -> SearchProfileRead:
    return SearchProfileRead.model_validate(search.update_profile(session, profile_id, data))


@router.delete(
    "/search/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["search"]
)
def delete_profile(session: SessionDep, profile_id: int) -> None:
    search.archive_profile(session, profile_id)


@router.get("/listings/{listing_id}", response_model=ListingRead, tags=["search"])
def get_listing(session: SessionDep, listing_id: int) -> ListingRead:
    return ListingRead.model_validate(search.get_listing(session, listing_id))


@router.post("/listings/{listing_id}/save", response_model=PostingDetail, tags=["search"])
def save_listing(
    session: SessionDep, registry: RegistryDep, listing_id: int, data: SaveListing
) -> PostingDetail:
    """Treffer merken: legt Stelle und Bewerbung an (mehrfacher Aufruf ist unschädlich)."""
    return PostingDetail.model_validate(search.save_listing(session, registry, listing_id, data))
