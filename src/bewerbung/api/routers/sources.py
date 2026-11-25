"""Quellen erkennen und Anzeigen importieren."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Query

from bewerbung.api.deps import FetcherDep, RegistryDep, SessionDep
from bewerbung.domain.schemas import ImportPreview, ImportRequest, SourceDetection
from bewerbung.services import importer, postings

router = APIRouter()


@router.get("/sources/detect", response_model=SourceDetection, tags=["sources"])
def detect_source(
    session: SessionDep, registry: RegistryDep, url: Annotated[str, Query(min_length=4)]
) -> SourceDetection:
    """Quelle, externe ID und mögliche Dublette zu einer eingefügten URL bestimmen."""
    return postings.detect_source(session, registry, url)


@router.post("/sources/import", response_model=ImportPreview, tags=["sources"])
async def import_preview(
    session: SessionDep, registry: RegistryDep, fetcher: FetcherDep, data: ImportRequest
) -> ImportPreview:
    """Anzeige laden und Felder vorschlagen. Speichert nichts; 502, wenn die Seite nicht lädt."""
    return await importer.preview_import(session, registry, fetcher, data.url)
