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
from bewerbung.config import Settings, get_settings
from bewerbung.db.migrate import upgrade_to_head
from bewerbung.db.session import build_engine, build_session_factory
from bewerbung.logging_config import configure_logging
from bewerbung.sources import default_registry

logger = logging.getLogger(__name__)

FRONTEND_DIST = Path(__file__).resolve().parents[2] / "frontend" / "dist"


def create_app(settings: Settings | None = None) -> FastAPI:
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
