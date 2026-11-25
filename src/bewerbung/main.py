"""App-Factory: verdrahtet Konfiguration, Datenbank, Quellen, API und Frontend."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bewerbung import __version__
from bewerbung.api.errors import register_error_handlers
from bewerbung.api.routes import router
from bewerbung.config import (
    Settings,
    get_settings,
    resolve_documents_dir,
    resolve_logos_dir,
)
from bewerbung.db.migrate import upgrade_to_head
from bewerbung.db.session import build_engine, build_session_factory
from bewerbung.letters.base import LetterGenerator
from bewerbung.letters.registry import build_generators
from bewerbung.logging_config import configure_logging
from bewerbung.search.aa_logos import AaLogoCache
from bewerbung.search.base import SearchProvider
from bewerbung.search.providers import build_providers
from bewerbung.services.documents import DocumentStore
from bewerbung.sources import default_registry
from bewerbung.sources.fetcher import HttpPageFetcher, PageFetcher

logger = logging.getLogger(__name__)

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_app(
    settings: Settings | None = None,
    page_fetcher: PageFetcher | None = None,
    search_providers: list[SearchProvider] | None = None,
    letter_generators: dict[str, LetterGenerator] | None = None,
    aa_logos: AaLogoCache | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if settings.auto_migrate:
            upgrade_to_head(settings.database_url)
        yield
        app.state.engine.dispose()

    app = FastAPI(title="Bewerbungsmanager", version=__version__, lifespan=lifespan)
    engine = build_engine(settings.database_url, echo=settings.sql_echo)
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)
    app.state.source_registry = default_registry()
    app.state.search_providers = (
        search_providers if search_providers is not None else build_providers(settings)
    )
    app.state.page_fetcher = page_fetcher or HttpPageFetcher(timeout=settings.fetch_timeout)
    app.state.letter_generators = (
        letter_generators if letter_generators is not None else build_generators(settings)
    )
    app.state.document_store = DocumentStore(resolve_documents_dir(settings))
    app.state.aa_logos = aa_logos or AaLogoCache(
        resolve_logos_dir(settings), settings.arbeitsagentur_api_key
    )
    app.state.max_upload_bytes = settings.max_upload_mb * 1024 * 1024

    register_error_handlers(app)
    app.include_router(router)
    _mount_frontend(app, FRONTEND_DIST)
    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """Liefert das gebaute React-Frontend aus; alle Nicht-API-Pfade gehen an ``index.html``."""
    index = dist / "index.html"
    if not index.is_file():
        logger.warning("Kein Frontend-Build unter %s, nur die API ist verfügbar", dist)
        return

    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Unbekannter API-Pfad")
        candidate = (dist / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(dist):
            return FileResponse(candidate)
        return FileResponse(index)
