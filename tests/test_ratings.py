from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from bewerbung.domain.ratings import RatingValue, aggregate, normalize


def test_normalize_and_aggregate() -> None:
    assert normalize(4.2) == 4.2
    assert normalize(78, 100) == 3.9
    with pytest.raises(ValueError, match="nicht zwischen"):
        normalize(6, 5)
    score = aggregate(
        [
            RatingValue("kununu", 3.8, 420),
            RatingValue("glassdoor", 4.4, 12),
            RatingValue("indeed", 2.0, 3),  # zu wenige
            RatingValue("google", 5.0, None),  # Anzahl unbekannt
        ]
    )
    assert score.mean == pytest.approx(4.1)  # arithmetisch, nicht nach Anzahl gewichtet
    assert score.sources == ["glassdoor", "kununu"]
    assert score.review_count == 432
    assert aggregate([RatingValue("kununu", 4.0, 5)]).mean is None


def test_rating_flow(client: TestClient) -> None:
    posting = client.post("/api/postings", json={"title": "Dev", "company_name": "ACME"}).json()
    cid = posting["company"]["id"]
    assert posting["company"]["employer_rating"] is None

    few = client.post(
        f"/api/companies/{cid}/ratings", json={"source": "kununu", "value": 3.6, "review_count": 4}
    )
    assert few.status_code == 201
    body = few.json()["employer_rating"]
    assert body["mean"] is None and body["current"][0]["rating"] == 3.6

    client.post(
        f"/api/companies/{cid}/ratings",
        json={"source": "kununu", "value": 3.8, "review_count": 120, "url": "kununu.com/de/acme"},
    )
    upd = client.post(
        f"/api/companies/{cid}/ratings",
        json={"source": "glassdoor", "value": 88, "scale_max": 100, "review_count": 40},
    ).json()
    r = upd["employer_rating"]
    assert r["mean"] == pytest.approx(4.1)
    assert r["sources"] == ["glassdoor", "kununu"]
    assert len(r["current"]) == 2  # je Portal nur der neueste Stand
    assert len(client.get(f"/api/companies/{cid}/ratings").json()) == 3  # Verlauf bleibt

    bad = client.post(
        f"/api/companies/{cid}/ratings", json={"source": "indeed", "value": 6, "scale_max": 5}
    )
    assert bad.status_code == 422

    detail = client.get(f"/api/postings/{posting['id']}").json()
    assert detail["company"]["employer_rating"]["mean"] == pytest.approx(4.1)
    ins = client.get(f"/api/postings/{posting['id']}/insights").json()
    assert ins["features"]["company"]["employer_rating"]["mean"] == pytest.approx(4.1)

    glassdoor = next(c for c in r["current"] if c["source"] == "glassdoor")
    after = client.delete(f"/api/companies/{cid}/ratings/{glassdoor['id']}").json()
    assert after["employer_rating"]["mean"] == pytest.approx(3.8)
    assert client.delete(f"/api/companies/{cid}/ratings/999").status_code == 404
