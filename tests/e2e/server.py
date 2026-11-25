"""Reproduzierbarer Server für die Playwright-Layouttests (frontend/e2e).

Startet die App mit leerer Temp-Datenbank und Fake-Portalen, legt ein paar Stellen,
Bewertungen und ein Profil an und liefert das gebaute Frontend aus. Kein Netzwerkzugriff.

    uv run python -m tests.e2e.server --port 8766
"""

from __future__ import annotations

import argparse
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.testclient import TestClient

from bewerbung.config import Settings
from bewerbung.domain.enums import JobSource
from bewerbung.main import create_app
from bewerbung.search.base import ListingDraft
from tests.test_search import FakeProvider

SOCIAL = {
    "hiringOrganization": {
        "name": "Nordlicht",
        "sameAs": [
            "https://www.linkedin.com/company/nordlicht-analytics",
            "https://www.kununu.com/de/nordlicht-analytics",
        ],
    }
}


Place = tuple[str, str, float, float]  # Ort, PLZ, Breite, Länge
HAMBURG: Place = ("Hamburg", "20095", 53.551, 9.993)


def _aa(ref: str, title: str, company: str, place: Place, *, desc: str, days: int) -> ListingDraft:
    city, plz, lat, lon = place
    raw = {
        "referenznummer": ref,
        "stellenlokationen": [
            {
                "adresse": {"ort": city, "plz": plz, "region": "HAMBURG"},
                "koordinaten": {"lat": lat, "lon": lon},
            }
        ],
        **(SOCIAL if company.startswith("Nordlicht") else {}),
    }
    return ListingDraft(
        source=JobSource.ARBEITSAGENTUR,
        external_id=ref,
        url=f"https://example.com/{ref}",
        title=title,
        company_name=company,
        location=city,
        description=desc,
        posted_at=datetime.now(UTC) - timedelta(days=days),
        raw=raw,
    )


# Bewusst mit überlangem Titel und Firmennamen: die häufigste Ursache für seitliches Scrollen.
HITS = [
    _aa("a1", "Data Engineer (m/w/d)", "Nordlicht Analytics GmbH", HAMBURG,
        desc="Python, SQL, Spark und AWS in einem agilen Team", days=3),
    _aa("a2", "Senior Python Entwickler Backend und Plattform-Architektur (m/w/d)",
        "Hafenwerk Logistik und Schifffahrtsdienstleistungen Aktiengesellschaft",
        ("Hamburg", "22769", 53.567, 9.94), desc="Python, Docker, Kubernetes, SQL", days=12),
    _aa("a3", "Data Analyst Controlling", "Kiesel Software", ("Lübeck", "23552", 53.866, 10.686),
        desc="Excel, Power BI, SQL", days=41),
    _aa("a4", "Werkstudent Data Science", "Nordlicht Analytics GmbH",
        ("Hamburg", "20457", 53.543, 9.985), desc="Python, Pandas, Machine Learning", days=1),
    _aa("a5", "Senior Data Engineer", "Brisa Energie SE", ("Kiel", "24103", 54.323, 10.135),
        desc="Spark, Python, Azure", days=6),
]  # fmt: skip
ADZUNA = [
    ListingDraft(
        source=JobSource.ADZUNA,
        external_id="z1",
        url="https://example.com/z1",
        title="Data Engineer m/w/d",
        company_name="Nordlicht Analytics",
        location="Hamburg",
        description="Python und SQL",
    )
]


def build_app(db: Path) -> FastAPI:
    settings = Settings(database_url=f"sqlite:///{db.as_posix()}", log_level="WARNING")
    providers = [
        FakeProvider(JobSource.ARBEITSAGENTUR, HITS),
        FakeProvider(JobSource.ADZUNA, ADZUNA),
    ]
    return create_app(settings, search_providers=providers)


def seed(client: TestClient) -> None:
    profile = {"skills": ["Python", "SQL", "Pandas", "Docker"], "home_location": "22769 Hamburg",
               "max_distance_km": 40}  # fmt: skip
    client.put("/api/profile", json=profile).raise_for_status()
    run = client.post("/api/search", json={"query": "data"}).json()
    ids = {h["listing"]["external_id"]: h["listing"]["id"] for h in run["hits"]}
    first = client.post(f"/api/listings/{ids['a1']}/save", json={}).json()
    second = client.post(f"/api/listings/{ids['a2']}/save", json={}).json()
    # Etwas Bewegung für die Kennzahlen-Szene: ein Gespräch, ein Angebot.
    for app, steps in (
        (first, ("applied", "interview")),
        (second, ("applied", "in_review", "offer")),
    ):
        for step in steps:
            app_id = app["application"]["id"]
            client.post(
                f"/api/applications/{app_id}/status", json={"status": step}
            ).raise_for_status()
    client.put("/api/profile", json=profile).raise_for_status()  # Wohnort jetzt verortbar
    cid = first["company"]["id"]
    for source, value, count in (("kununu", 3.9, 214), ("glassdoor", 4.3, 37), ("indeed", 3.0, 6)):
        client.post(
            f"/api/companies/{cid}/ratings",
            json={"source": source, "value": value, "review_count": count},
        ).raise_for_status()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    db = Path(tempfile.mkdtemp(prefix="anheuern-e2e-")) / "e2e.db"
    with TestClient(build_app(db)) as client:
        seed(client)
    uvicorn.run(build_app(db), host="127.0.0.1", port=args.port, log_level="warning")


if __name__ == "__main__":
    main()
