from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from bewerbung.config import Settings
from bewerbung.domain.tags import clean_tag, extract_hashtags, unique_tags


def test_clean_and_extract() -> None:
    assert clean_tag("  #Machine Learning ") == "Machine-Learning"
    assert unique_tags(["Python", "#python", "PYTHON", "remote"]) == ["Python", "remote"]
    assert extract_hashtags(
        "Gespräch gut, #remote möglich. #Python. kein#tag, ##x, #gehalt-70k!"
    ) == [
        "remote",
        "Python",
        "gehalt-70k",
    ]
    with pytest.raises(ValueError, match="leer"):
        clean_tag("#")
    with pytest.raises(ValueError, match="Ungültiger"):
        clean_tag("a/b")


def test_tags_on_create_update_and_filter(client: TestClient, make_posting) -> None:
    a = make_posting(title="A", tags=["#Python", "remote", "python"])
    b = make_posting(title="B", tags=["Python"])
    make_posting(title="C")
    assert a["tags"] == ["Python", "remote"]

    def titles(**params: object) -> list[str]:
        resp = client.get("/api/postings", params=params)
        assert resp.status_code == 200, resp.text
        return sorted(p["title"] for p in resp.json()["items"])

    assert titles(tag="python") == ["A", "B"]
    assert titles(tag=["#PYTHON", "Remote"]) == ["A"]  # UND-Verknüpfung, Schreibweise egal
    assert titles(tag="unbekannt") == []
    assert client.get("/api/postings", params={"tag": "a/b"}).status_code == 422

    assert client.get("/api/tags").json() == [
        {"name": "Python", "count": 2, "derived": False},
        {"name": "remote", "count": 1, "derived": False},
    ]

    upd = client.patch(f"/api/postings/{b['id']}", json={"tags": ["hamburg"]}).json()
    assert upd["tags"] == ["hamburg"]
    assert titles(tag="python") == ["A"]
    # Andere Felder ändern lässt die Tags in Ruhe.
    assert client.patch(f"/api/postings/{b['id']}", json={"title": "B2"}).json()["tags"] == [
        "hamburg"
    ]


def test_removed_tags_are_kept_as_history(
    client: TestClient, make_posting, settings: Settings
) -> None:
    p = make_posting(tags=["python"])
    client.patch(f"/api/postings/{p['id']}", json={"tags": []})
    client.patch(f"/api/postings/{p['id']}", json={"tags": ["python"]})

    with create_engine(settings.database_url).connect() as conn:
        rows = conn.execute(
            text(
                "SELECT ended_at IS NULL FROM tag_links WHERE entity_type = 'posting' AND entity_id = :id ORDER BY id"
            ),
            {"id": p["id"]},
        ).all()
    assert [r[0] for r in rows] == [0, 1]  # erste Zuordnung beendet, zweite aktiv


def test_hashtags_in_notes_tag_the_posting(client: TestClient, make_posting) -> None:
    p = make_posting(tags=["python"])
    app_id = p["application"]["id"]
    resp = client.post(
        f"/api/applications/{app_id}/notes",
        json={"body": "Recruiterin meint #remote geht, #Python wichtig"},
    )
    assert resp.status_code == 201, resp.text
    detail = client.get(f"/api/postings/{p['id']}").json()
    assert detail["tags"] == ["python", "remote"]


def test_archived_postings_not_counted(client: TestClient, make_posting) -> None:
    p = make_posting(tags=["alt"])
    client.post(f"/api/postings/{p['id']}/archive")
    assert client.get("/api/tags").json() == []
