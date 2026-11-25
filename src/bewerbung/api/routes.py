"""REST-Endpunkte unter ``/api``, nach Themen in ``api/routers`` aufgeteilt.

Dünne Schicht: Validierung -> Service -> Schema. Dieses Modul setzt nur zusammen.
"""

from __future__ import annotations

from fastapi import APIRouter

from bewerbung.api.routers import (
    applications,
    companies,
    documents,
    insights,
    letters,
    meta,
    postings,
    search,
    sources,
    tags,
)

router = APIRouter(prefix="/api")
for _module in (
    meta,
    companies,
    sources,
    postings,
    applications,
    search,
    insights,
    tags,
    letters,
    documents,
):
    router.include_router(_module.router)
