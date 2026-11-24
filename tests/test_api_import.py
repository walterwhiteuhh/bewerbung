from __future__ import annotations

import asyncio
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bewerbung.config import Settings
from bewerbung.main import create_app
from bewerbung.sources.fetcher import FetchError, HttpPageFetcher

FIXTURES = Path(__file__).parent / "fixtures"
STEPSTONE = (
    "https://www.stepstone.de/stellenangebote--Data-Scientist-Hamburg-ACME--12345678-inline.html"
)


class FakeFetcher:
    def __init__(self, pages: dict[str, str]) -> None:
        self.pages = pages
        self.requested: list[str] = []

    async def fetch(self, url: str) -> str:
        self.requested.append(url)
        if url not in self.pages:
            raise FetchError("Die Seite verweigert den automatischen Abruf (999)")
        return self.pages[url]


@pytest.fixture
def fetcher() -> FakeFetcher:
    html = (FIXTURES / "stepstone_jsonld.html").read_text(encoding="utf-8")
    return FakeFetcher(
        {
            STEPSTONE: html,
            "https://linkedin.com/jobs/view/3912345678": html,
        }
    )


@pytest.fixture
def import_client(settings: Settings, fetcher: FakeFetcher) -> Iterator[TestClient]:
    with TestClient(create_app(settings, page_fetcher=fetcher)) as c:
        yield c


def test_import_preview_and_create(import_client: TestClient) -> None:
    resp = import_client.post("/api/sources/import", json={"url": STEPSTONE})
    assert resp.status_code == 200, resp.text
    preview = resp.json()
    assert preview["detection"]["source"] == "stepstone"
    assert preview["method"] == "json-ld"
    assert preview["company_name"] == "ACME Analytics GmbH"
    assert preview["salary_min"] == 60000
    assert preview["raw_payload"]["extractor"]["method"] == "json-ld"
    assert preview["warnings"] == []

    # Vorschau speichert nichts
    assert import_client.get("/api/postings").json()["total"] == 0

    fields = {
        k: preview[k]
        for k in ("title", "company_name", "location", "remote_type", "salary_min", "salary_max")
    }
    created = import_client.post(
        "/api/postings", json={**fields, "url": STEPSTONE, "raw_payload": preview["raw_payload"]}
    )
    assert created.status_code == 201

    again = import_client.post("/api/sources/import", json={"url": STEPSTONE}).json()
    assert again["detection"]["duplicate_of"] == created.json()["id"]
    assert "bereits erfasst" in again["warnings"][0]


def test_linkedin_search_url_fetches_detail_page(
    import_client: TestClient, fetcher: FakeFetcher
) -> None:
    url = "https://www.linkedin.com/jobs/search/?currentJobId=3912345678&keywords=data"
    assert import_client.post("/api/sources/import", json={"url": url}).status_code == 200
    assert fetcher.requested == ["https://linkedin.com/jobs/view/3912345678"]


def test_blocked_page_returns_502(import_client: TestClient) -> None:
    resp = import_client.post("/api/sources/import", json={"url": "https://example.com/job/1"})
    assert resp.status_code == 502
    assert "verweigert" in resp.json()["detail"]


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("http://127.0.0.1:8000/api/health", "Interne oder lokale"),
        ("http://localhost/", "Interne oder lokale"),
        ("ftp://example.com/x", "Nur http"),
    ],
)
def test_fetcher_blocks_internal_targets(url: str, message: str) -> None:
    with pytest.raises(FetchError, match=message):
        asyncio.run(HttpPageFetcher().fetch(url))
