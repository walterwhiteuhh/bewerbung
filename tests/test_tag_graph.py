"""Hashtags übergreifend: Verknüpfungen (Ober-/Unterbegriff, Synonym) und Tags an Firmen,
Unterlagen und gespeicherten Suchen."""

from __future__ import annotations

from fastapi.testclient import TestClient


def _titles(client: TestClient, **params: object) -> list[str]:
    resp = client.get("/api/postings", params=params)
    assert resp.status_code == 200, resp.text
    return sorted(p["title"] for p in resp.json()["items"])


def test_filter_expands_over_seeded_relations(client: TestClient, make_posting) -> None:
    make_posting(title="Web", tags=["react"])  # react -> frontend (Startverknüpfung)
    make_posting(title="Api", tags=["java"])  # java -> backend
    make_posting(title="Sonst", tags=["scrum"])

    assert _titles(client, tag="frontend") == ["Web"]  # Unterbegriff gefunden
    assert _titles(client, tag="javascript") == ["Web"]  # react -> javascript, mehrere Oberbegriffe
    assert _titles(client, tag="react") == ["Web"]
    assert _titles(client, tag=["frontend", "react"]) == ["Web"]
    assert _titles(client, tag=["frontend", "backend"]) == []  # UND bleibt UND
    assert _titles(client, tag="ai") == []  # Synonym ki<->ai, aber keine Stelle mit KI-Tag


def test_alias_matches_both_directions(client: TestClient, make_posting) -> None:
    make_posting(title="Mit KI", tags=["KI"])
    make_posting(title="Mit AI", tags=["AI"])
    assert _titles(client, tag="ki") == ["Mit AI", "Mit KI"]
    assert _titles(client, tag="ai") == ["Mit AI", "Mit KI"]


def test_tag_list_shows_derived_parents(client: TestClient, make_posting) -> None:
    make_posting(title="A", tags=["react"])
    make_posting(title="B", tags=["angular"])
    tags = {t["name"]: t for t in client.get("/api/tags").json()}
    assert tags["frontend"] == {"name": "frontend", "count": 2, "derived": True}
    assert tags["react"]["derived"] is False
    assert tags["react"]["count"] == 1


def test_manage_relations_and_reject_cycles(client: TestClient, make_posting) -> None:
    make_posting(title="Hund", tags=["Pudel"])
    assert _titles(client, tag="Tier") == []
    rel = client.post(
        "/api/tags/relations", json={"tag": "Pudel", "related": "Tier", "kind": "implies"}
    )
    assert rel.status_code == 201, rel.text
    assert _titles(client, tag="tier") == ["Hund"]
    # Zweimal anlegen bleibt eine Verknüpfung
    again = client.post(
        "/api/tags/relations", json={"tag": "pudel", "related": "tier", "kind": "implies"}
    )
    assert again.json()["id"] == rel.json()["id"]
    # Kreis und Selbstbezug werden abgelehnt
    assert (
        client.post(
            "/api/tags/relations", json={"tag": "Tier", "related": "Pudel", "kind": "implies"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/tags/relations", json={"tag": "x", "related": "X", "kind": "alias"}
        ).status_code
        == 400
    )
    # Löschen beendet die Verknüpfung (Zeile bleibt als Historie)
    assert client.delete(f"/api/tags/relations/{rel.json()['id']}").status_code == 204
    assert _titles(client, tag="tier") == []
    assert client.delete(f"/api/tags/relations/{rel.json()['id']}").status_code == 404


def test_seeded_relation_stays_removed(client: TestClient) -> None:
    rels = client.get("/api/tags/relations").json()
    assert any(r["tag"] == "react" and r["related"] == "frontend" for r in rels)
    seed = next(r for r in rels if r["tag"] == "react" and r["related"] == "frontend")
    assert seed["origin"] == "seed"
    client.delete(f"/api/tags/relations/{seed['id']}")
    rels = client.get("/api/tags/relations").json()
    assert not any(r["tag"] == "react" and r["related"] == "frontend" for r in rels)


def test_tags_on_companies_documents_and_searches(client: TestClient, make_posting) -> None:
    posting = make_posting(title="Job", company_name="Nordlicht GmbH", tags=["python"])
    company_id = client.get("/api/companies").json()[0]["id"]
    profile = client.post("/api/search/profiles", json={"name": "Py HH", "query": "python"}).json()

    assert client.put(
        f"/api/tag-links/company/{company_id}", json={"tags": ["Wunscharbeitgeber", "#Hamburg"]}
    ).json() == ["Hamburg", "Wunscharbeitgeber"]
    assert client.put(
        f"/api/tag-links/search_profile/{profile['id']}", json={"tags": ["Python"]}
    ).json() == ["python"]  # erste Schreibweise gewinnt
    assert client.get("/api/tag-links/company").json() == {
        str(company_id): ["Hamburg", "Wunscharbeitgeber"]
    }
    # Ersetzen beendet die alten Zuordnungen
    client.put(f"/api/tag-links/company/{company_id}", json={"tags": ["Hamburg"]})
    assert client.get("/api/tag-links/company").json() == {str(company_id): ["Hamburg"]}

    # Übergreifende Sicht: derselbe Hashtag über Stellen, Firmen, Suchen
    ov = client.get("/api/tags/python/overview").json()
    assert [p["id"] for p in ov["postings"]] == [posting["id"]]
    assert [s["label"] for s in ov["search_profile"]] == ["Py HH"]
    assert [c["label"] for c in ov["company"]] == ["Nordlicht GmbH"]  # über die Stelle
    ov = client.get("/api/tags/hamburg/overview").json()
    assert [c["label"] for c in ov["company"]] == ["Nordlicht GmbH"]  # direkt gesetzt

    # Fehler: unbekannter Typ, fehlendes Objekt, unbekannter Hashtag
    assert client.put("/api/tag-links/blub/1", json={"tags": ["x"]}).status_code == 400
    assert client.put("/api/tag-links/company/9999", json={"tags": ["x"]}).status_code == 404
    assert client.get("/api/tags/gibtsnicht/overview").status_code == 404


def test_related_tags_from_hints_and_cooccurrence(client: TestClient, make_posting) -> None:
    make_posting(title="A", tags=["python", "pandas", "docker"])
    make_posting(title="B", tags=["python", "docker"])
    ov = client.get("/api/tags/python/overview").json()
    # python hat Unterbegriff pandas (im Filter enthalten); docker kommt oft dazu
    assert "pandas" in ov["includes"]
    assert ov["related"][0].lower() == "data-science" or "docker" in [
        r.lower() for r in ov["related"]
    ]
    assert "docker" in [r.lower() for r in ov["related"]]
