from __future__ import annotations

from fastapi.testclient import TestClient

LINKEDIN = "https://www.linkedin.com/jobs/view/python-developer-3912345678/?trk=x"


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


def test_create_detects_source_and_starts_history(make_posting) -> None:
    posting = make_posting(url=LINKEDIN, location="Hamburg", remote_type="hybrid")
    assert posting["source"] == "linkedin"
    assert posting["external_id"] == "3912345678"
    assert posting["company"]["name"] == "ACME GmbH"
    app = posting["application"]
    assert app["current_status"] == "saved"
    assert app["applied_at"] is None
    assert [e["to_status"] for e in app["events"]] == ["saved"]
    assert posting["created_at"].endswith(("+00:00", "Z"))


def test_manual_posting_without_url(make_posting) -> None:
    assert make_posting()["source"] == "manual"


def test_duplicate_is_rejected(client: TestClient, make_posting) -> None:
    first = make_posting(url=LINKEDIN)
    resp = client.post(
        "/api/postings",
        json={"title": "x", "url": "https://de.linkedin.com/jobs/view/3912345678"},
    )
    assert resp.status_code == 409
    assert resp.json()["existing_id"] == first["id"]

    detect = client.get("/api/sources/detect", params={"url": LINKEDIN}).json()
    assert detect["duplicate_of"] == first["id"]


def test_companies_are_merged_by_normalized_name(make_posting) -> None:
    a = make_posting(company_name="SAP SE")
    b = make_posting(company_name="  sap  ")
    assert a["company"]["id"] == b["company"]["id"]


def test_validation_salary_range(client: TestClient) -> None:
    resp = client.post(
        "/api/postings", json={"title": "x", "salary_min": 90000, "salary_max": 50000}
    )
    assert resp.status_code == 422


def test_update_posting(client: TestClient, make_posting) -> None:
    posting = make_posting()
    resp = client.patch(
        f"/api/postings/{posting['id']}",
        json={"location": "Berlin", "company_name": "Neue Firma", "salary_min": 60000},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["location"] == "Berlin"
    assert body["company"]["name"] == "Neue Firma"
    assert body["title"] == "Data Scientist"


def test_list_filter_search_and_archive(client: TestClient, make_posting) -> None:
    a = make_posting(title="Python Backend Engineer", url=LINKEDIN)
    b = make_posting(title="Data Analyst", company_name="Hamburg Data AG", initial_status="applied")
    make_posting(title="Frontend Dev", company_name="Other")

    def ids(**params: object) -> list[int]:
        resp = client.get("/api/postings", params=params)
        assert resp.status_code == 200, resp.text
        return [i["id"] for i in resp.json()["items"]]

    assert len(ids()) == 3
    assert ids(q="python") == [a["id"]]
    assert ids(q="hamburg") == [b["id"]]  # Suche greift auch auf den Firmennamen
    assert ids(status="applied") == [b["id"]]
    assert set(ids(status=["applied", "saved"])) == {a["id"], b["id"], *ids(q="frontend")}
    assert ids(source="linkedin") == [a["id"]]
    assert ids(sort="title", order="asc")[0] == b["id"]

    assert client.post(f"/api/postings/{a['id']}/archive").json()["archived_at"] is not None
    assert a["id"] not in ids()
    assert a["id"] in ids(include_archived=True)
    client.post(f"/api/postings/{a['id']}/restore")
    assert a["id"] in ids()


def test_pagination_total(client: TestClient, make_posting) -> None:
    for i in range(5):
        make_posting(title=f"Job {i}")
    page = client.get("/api/postings", params={"limit": 2, "offset": 2}).json()
    assert page["total"] == 5
    assert len(page["items"]) == 2


def test_not_found(client: TestClient) -> None:
    assert client.get("/api/postings/999").status_code == 404
