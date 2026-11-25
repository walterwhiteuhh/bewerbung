"""Merkmale (Features) und Auswertungen zu Anzeigen."""

from __future__ import annotations

import csv
import io

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from bewerbung.api.deps import SessionDep
from bewerbung.domain.schemas import JobFeatures, PostingInsights
from bewerbung.services import insights, search

router = APIRouter()


@router.get("/listings/{listing_id}/features", response_model=JobFeatures, tags=["insights"])
def listing_features(session: SessionDep, listing_id: int) -> JobFeatures:
    listing = search.get_listing(session, listing_id)
    return insights.listing_features(session, [listing])[listing.id]


@router.get("/postings/{posting_id}/insights", response_model=PostingInsights, tags=["insights"])
def posting_insights(session: SessionDep, posting_id: int) -> PostingInsights:
    """Querbezüge: andere Portale, gleiche Firma, ähnliche Stellen, Merkmale."""
    return insights.posting_insights(session, posting_id)


@router.get("/insights/listings.csv", tags=["insights"])
def export_features(session: SessionDep) -> StreamingResponse:
    """Alle Anzeigen mit Merkmalen als CSV (Semikolon, UTF-8 mit BOM für Excel)."""
    rows = list(insights.features_rows(session))  # Session lebt nur während der Anfrage
    buf = io.StringIO()
    buf.write("\ufeff")
    fields = list(rows[0]) if rows else list(insights.EXPORT_COLUMNS)
    writer = csv.DictWriter(buf, fieldnames=fields, delimiter=";")
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="anzeigen-merkmale.csv"'},
    )
