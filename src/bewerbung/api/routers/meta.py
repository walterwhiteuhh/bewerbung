"""Health-Check und Kennzahlen."""

from __future__ import annotations

from fastapi import APIRouter

from bewerbung.api.deps import SessionDep
from bewerbung.domain.schemas import Stats
from bewerbung.services import stats

router = APIRouter()


@router.get("/health", tags=["meta"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/stats", response_model=Stats, tags=["stats"])
def get_stats(session: SessionDep) -> Stats:
    return stats.compute_stats(session)
