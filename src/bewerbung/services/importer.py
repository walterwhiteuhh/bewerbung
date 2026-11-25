"""Import-Vorschau: URL erkennen, Seite laden, Stellendaten extrahieren."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from bewerbung.db.types import utcnow
from bewerbung.domain.keywords import suggest_tags
from bewerbung.domain.schemas import ImportPreview
from bewerbung.services.postings import detect_source
from bewerbung.sources import SourceRegistry
from bewerbung.sources.extract import EXTRACTOR_VERSION, extract_posting, looks_like_challenge
from bewerbung.sources.fetcher import FetchError, PageFetcher

logger = logging.getLogger(__name__)

_MAX_DESCRIPTION = 50_000


async def preview_import(
    session: Session, registry: SourceRegistry, fetcher: PageFetcher, url: str
) -> ImportPreview:
    detection = detect_source(session, registry, url)
    adapter = registry.adapter_for(url)
    reference = registry.identify(url)
    target = adapter.fetch_url(reference, url)

    html = await fetcher.fetch(target)  # FetchError geht als 502 an die API
    extracted = extract_posting(html)
    if looks_like_challenge(html, extracted):
        raise FetchError(
            "Die Seite zeigt eine Bot-Prüfung (Captcha) statt der Anzeige,"
            " bitte Daten manuell eintragen"
        )

    warnings: list[str] = []
    if extracted.method == "none":
        warnings.append("Auf der Seite wurden keine Stellendaten gefunden.")
    elif extracted.method == "opengraph":
        warnings.append("Nur Titel und Beschreibung gefunden, bitte Firma und Ort ergänzen.")
    if detection.duplicate_of is not None:
        warnings.append("Diese Stelle ist bereits erfasst.")

    description = extracted.description
    if description and len(description) > _MAX_DESCRIPTION:
        description = description[:_MAX_DESCRIPTION].rstrip() + " …"

    logger.info("Import-Vorschau %s: Methode %s", detection.source, extracted.method)
    return ImportPreview(
        detection=detection,
        method=extracted.method,
        title=extracted.title,
        company_name=extracted.company_name,
        location=extracted.location,
        remote_type=extracted.remote_type,
        employment_type=extracted.employment_type,
        salary_min=extracted.salary_min,
        salary_max=extracted.salary_max,
        salary_currency=extracted.salary_currency,
        description=description,
        posted_at=extracted.posted_at,
        raw_payload={
            "fetched_url": target,
            "fetched_at": utcnow().isoformat(),
            "extractor": {"method": extracted.method, "version": EXTRACTOR_VERSION},
            **extracted.raw,
        },
        suggested_tags=suggest_tags(
            title=extracted.title,
            description=description,
            location=extracted.location,
            remote_type=extracted.remote_type,
            employment_type=extracted.employment_type,
        ),
        warnings=warnings,
    )
