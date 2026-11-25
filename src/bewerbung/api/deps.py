"""FastAPI-Abhängigkeiten. Engine und Registry hängen am ``app.state`` (testbar austauschbar)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from bewerbung.db.session import session_scope
from bewerbung.letters.base import LetterGenerator
from bewerbung.search.aa_logos import AaLogoCache
from bewerbung.search.base import SearchProvider
from bewerbung.services.documents import DocumentStore
from bewerbung.sources import SourceRegistry
from bewerbung.sources.fetcher import PageFetcher
from bewerbung.sources.site_logo import LogoStore, SiteLogoFetcher


def get_session(request: Request) -> Iterator[Session]:
    yield from session_scope(request.app.state.session_factory)


def get_registry(request: Request) -> SourceRegistry:
    registry: SourceRegistry = request.app.state.source_registry
    return registry


def get_fetcher(request: Request) -> PageFetcher:
    fetcher: PageFetcher = request.app.state.page_fetcher
    return fetcher


def get_providers(request: Request) -> list[SearchProvider]:
    providers: list[SearchProvider] = request.app.state.search_providers
    return providers


def get_letter_generators(request: Request) -> dict[str, LetterGenerator]:
    generators: dict[str, LetterGenerator] = request.app.state.letter_generators
    return generators


def get_document_store(request: Request) -> DocumentStore:
    store: DocumentStore = request.app.state.document_store
    return store


def get_aa_logos(request: Request) -> AaLogoCache:
    cache: AaLogoCache = request.app.state.aa_logos
    return cache


def get_logo_store(request: Request) -> LogoStore:
    store: LogoStore = request.app.state.logo_store
    return store


def get_site_logos(request: Request) -> SiteLogoFetcher:
    fetcher: SiteLogoFetcher = request.app.state.site_logos
    return fetcher


SessionDep = Annotated[Session, Depends(get_session)]
RegistryDep = Annotated[SourceRegistry, Depends(get_registry)]
FetcherDep = Annotated[PageFetcher, Depends(get_fetcher)]
ProvidersDep = Annotated[list[SearchProvider], Depends(get_providers)]
LetterGeneratorsDep = Annotated[dict[str, LetterGenerator], Depends(get_letter_generators)]
DocumentStoreDep = Annotated[DocumentStore, Depends(get_document_store)]
AaLogosDep = Annotated[AaLogoCache, Depends(get_aa_logos)]
LogoStoreDep = Annotated[LogoStore, Depends(get_logo_store)]
SiteLogosDep = Annotated[SiteLogoFetcher, Depends(get_site_logos)]
