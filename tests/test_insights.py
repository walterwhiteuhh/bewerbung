from __future__ import annotations

import csv
import io
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from bewerbung.config import Settings
from bewerbung.domain.enums import JobSource
from bewerbung.domain.geo import city_key, haversine_km, place_from_payload, place_from_text
from bewerbung.domain.matching import JobProfile, similarity, title_key
from bewerbung.main import create_app
from bewerbung.search.base import ListingDraft
from tests.test_search import FakeProvider


def aa_item(refnr: str, ort: str, plz: str, lat: float, lon: float) -> dict:
    return {
        "referenznummer": refnr,
        "stellenlokationen": [
            {
                "adresse": {"ort": ort, "plz": plz, "region": "HAMBURG"},
                "koordinaten": {"lat": lat, "lon": lon},
            }
        ],
    }


def test_title_key_and_similarity() -> None:
    assert title_key("Data Engineer (m/w/d)") == title_key("Data Engineer m/w/d")
    assert title_key("Verkäufer*in (all genders)") == "verkäufer"
    a = JobProfile.build("Python Data Engineer (m/w/d)", "SQL, Spark, AWS")
    b = JobProfile.build("Data Engineer Python", "Wir nutzen Spark und SQL")
    c = JobProfile.build("Pflegefachkraft", "Pflege im Schichtdienst")
    assert similarity(a, b).score > 0.6
    assert similarity(a, c).score == 0
    assert "spark" in similarity(a, b).shared_skills


def test_geo_helpers() -> None:
    assert haversine_km(53.55, 10.0, 52.52, 13.405) == pytest.approx(255, abs=5)  # HH -> B
    place = place_from_payload(aa_item("1", "Hamburg", "20095", 53.55, 9.99))
    assert (place.city, place.postal_code, place.region) == ("Hamburg", "20095", "Hamburg")
    assert place.has_coords
    ld = {
        "json_ld": {
            "jobLocation": {
                "address": {"addressLocality": "Kiel", "postalCode": "24103"},
                "geo": {"latitude": "54.32", "longitude": "10.13"},
            }
        }
    }
    assert place_from_payload(ld).lat == pytest.approx(54.32)
    assert place_from_text("22769 Hamburg, Altona").postal_code == "22769"
    assert place_from_text("Remote").city is None
    assert city_key("Hamburg-Altona") == "hamburg"


@pytest.fixture
def client_with_hits(settings: Settings) -> Iterator[TestClient]:
    aa = FakeProvider(
        JobSource.ARBEITSAGENTUR,
        [
            ListingDraft(
                source=JobSource.ARBEITSAGENTUR,
                external_id="a1",
                url=None,
                title="Data Engineer (m/w/d)",
                company_name="ACME GmbH",
                description="Python, SQL und Spark",
                raw=aa_item("a1", "Hamburg", "20095", 53.55, 9.99),
            ),
            ListingDraft(
                source=JobSource.ARBEITSAGENTUR,
                external_id="a2",
                url=None,
                title="Werkstudent Controlling",
                company_name="ACME",
                description="Excel",
                raw=aa_item("a2", "Kiel", "24103", 54.32, 10.13),
            ),
        ],
    )
    other = FakeProvider(
        JobSource.ADZUNA,
        [
            ListingDraft(
                source=JobSource.ADZUNA,
                external_id="z1",
                url=None,
                title="Data Engineer m/w/d",
                company_name="Acme GmbH",
                location="Hamburg",
                description="Python und SQL",
            )
        ],
    )
    with TestClient(create_app(settings, search_providers=[aa, other])) as c:
        yield c


def test_search_hits_carry_features(client_with_hits: TestClient) -> None:
    c = client_with_hits
    c.put(
        "/api/profile",
        json={"skills": ["Python", "SQL"], "home_location": "20095 Hamburg", "max_distance_km": 50},
    )
    run = c.post("/api/search", json={"query": "data"}).json()
    by_ext = {h["listing"]["external_id"]: h for h in run["hits"]}
    f = by_ext["a1"]["features"]
    assert f["distance_km"] == 0
    assert (f["lat"], f["lon"], f["postal_code"]) == (53.55, 9.99, "20095")
    assert f["position_estimated"] is False
    assert f["within_max_distance"] is True
    assert sorted(f["portals"]) == ["adzuna", "arbeitsagentur"]  # gleiche Stelle, 2 Portale
    assert f["company"]["listings"] == 3  # ACME GmbH / ACME / Acme GmbH = eine Firma
    # python + sql von python/sql/spark/data-engineering
    assert f["match_score"] == pytest.approx(0.5)
    assert "spark" in f["missing_skills"]
    kiel = by_ext["a2"]["features"]
    assert kiel["distance_km"] == pytest.approx(87, abs=5)
    assert kiel["within_max_distance"] is False
    # Adzuna ohne Koordinaten: Entfernung über die Stadtmitte aus anderen Anzeigen geschätzt.
    z = by_ext["z1"]["features"]
    assert z["distance_estimated"] is True and z["distance_km"] == 0
    assert z["position_estimated"] is True and z["lat"] == pytest.approx(53.55)

    profile = c.get("/api/profile").json()
    assert profile["home_located"] is True
    assert profile["home_lat"] == pytest.approx(53.55)


def test_posting_insights_and_export(client_with_hits: TestClient) -> None:
    c = client_with_hits
    run = c.post("/api/search", json={"query": "data"}).json()
    by_ext = {h["listing"]["external_id"]: h["listing"]["id"] for h in run["hits"]}
    posting = c.post(f"/api/listings/{by_ext['a1']}/save", json={}).json()

    ins = c.get(f"/api/postings/{posting['id']}/insights").json()
    assert [b["source"] for b in ins["other_portals"]] == ["adzuna"]
    assert [b["title"] for b in ins["same_company_listings"]] == ["Werkstudent Controlling"]
    assert ins["features"]["company"]["saved_postings"] == 1
    assert any(s["kind"] == "listing" for s in ins["similar"]) or ins["similar"] == []

    # Ein Treffer derselben Firma verweist jetzt auf die gemerkte, ähnliche Stelle.
    feats = c.get(f"/api/listings/{by_ext['z1']}/features").json()
    assert feats["similar_saved"]["id"] == posting["id"]

    resp = c.get("/api/insights/listings.csv")
    assert resp.status_code == 200
    rows = list(csv.DictReader(io.StringIO(resp.text.lstrip("﻿")), delimiter=";"))
    assert len(rows) == 3
    saved = next(r for r in rows if r["posting_id"])
    assert saved["label_status"] == "saved"
    assert {"distance_km", "match_score", "portal_count", "company_listings"} <= set(rows[0])
