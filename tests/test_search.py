from __future__ import annotations

import asyncio
from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from bewerbung.config import Settings
from bewerbung.domain.enums import JobSource, RemoteType
from bewerbung.main import create_app
from bewerbung.search.adzuna import AdzunaProvider
from bewerbung.search.arbeitsagentur import ArbeitsagenturProvider, to_draft
from bewerbung.search.base import ListingDraft, ProviderError, SearchQuery


class FakeProvider:
    def __init__(
        self,
        source: JobSource,
        drafts: list[ListingDraft],
        fail: str | None = None,
        unavailable: str | None = None,
    ) -> None:
        self.source = source
        self.label = source.value
        self.drafts = drafts
        self.fail = fail
        self._unavailable = unavailable
        self.queries: list[SearchQuery] = []

    @property
    def unavailable_reason(self) -> str | None:
        return self._unavailable

    async def search(self, query: SearchQuery) -> list[ListingDraft]:
        self.queries.append(query)
        if self.fail:
            raise ProviderError(self.fail)
        return self.drafts


def draft(source: JobSource, ext: str, title: str, **kw: object) -> ListingDraft:
    return ListingDraft(source=source, external_id=ext, url=kw.pop("url", None), title=title, **kw)  # type: ignore[arg-type]


@pytest.fixture
def aa() -> FakeProvider:
    return FakeProvider(
        JobSource.ARBEITSAGENTUR,
        [
            draft(
                JobSource.ARBEITSAGENTUR,
                "10000-1",
                "Data Scientist",
                company_name="ACME GmbH",
                url="https://www.arbeitsagentur.de/jobsuche/jobdetail/10000-1",
            ),
            draft(JobSource.ARBEITSAGENTUR, "10000-2", "Data Engineer", company_name="Beta AG"),
        ],
    )


@pytest.fixture
def adz() -> FakeProvider:
    return FakeProvider(JobSource.ADZUNA, [draft(JobSource.ADZUNA, "991", "ML Engineer")])


@pytest.fixture
def search_client(settings: Settings, aa: FakeProvider, adz: FakeProvider) -> Iterator[TestClient]:
    with TestClient(create_app(settings, search_providers=[aa, adz])) as c:
        yield c


def test_providers_endpoint(settings: Settings) -> None:
    off = FakeProvider(JobSource.ADZUNA, [], unavailable="API-Key fehlt")
    with TestClient(create_app(settings, search_providers=[off])) as c:
        info = c.get("/api/search/providers").json()
    assert info == [
        {"source": "adzuna", "label": "adzuna", "available": False, "reason": "API-Key fehlt"}
    ]


def test_search_interleaves_and_records_run(search_client: TestClient, aa: FakeProvider) -> None:
    run = search_client.post(
        "/api/search", json={"query": "data", "location": "Hamburg", "radius_km": 25}
    ).json()
    titles = [h["listing"]["title"] for h in run["hits"]]
    assert titles == ["Data Scientist", "ML Engineer", "Data Engineer"]  # abwechselnd je Quelle
    assert [h["rank"] for h in run["hits"]] == [1, 2, 3]
    assert run["total_hits"] == 3
    assert run["new_hits"] == 3
    assert run["errors"] == []
    assert aa.queries[0].location == "Hamburg"
    assert aa.queries[0].radius_km == 25

    again = search_client.post("/api/search", json={"query": "data"}).json()
    assert again["new_hits"] == 0
    assert again["hits"][0]["listing"]["id"] == run["hits"][0]["listing"]["id"]
    assert len(search_client.get("/api/search/runs").json()) == 2


def test_source_filter_and_provider_errors(settings: Settings, aa: FakeProvider) -> None:
    broken = FakeProvider(JobSource.ADZUNA, [], fail="Adzuna antwortet mit 500")
    with TestClient(create_app(settings, search_providers=[aa, broken])) as c:
        run = c.post("/api/search", json={"query": "x"}).json()
        assert run["total_hits"] == 2
        assert run["errors"] == [{"source": "adzuna", "message": "Adzuna antwortet mit 500"}]

        only_aa = c.post("/api/search", json={"query": "x", "sources": ["arbeitsagentur"]}).json()
        assert only_aa["sources"] == ["arbeitsagentur"]
        assert only_aa["errors"] == []


def test_listing_update_on_changed_content(search_client: TestClient, aa: FakeProvider) -> None:
    first = search_client.post("/api/search", json={"query": "x"}).json()
    listing_id = first["hits"][0]["listing"]["id"]
    aa.drafts[0] = aa.drafts[0].model_copy(update={"title": "Senior Data Scientist"})
    search_client.post("/api/search", json={"query": "x"})
    listing = search_client.get(f"/api/listings/{listing_id}").json()
    assert listing["title"] == "Senior Data Scientist"
    assert listing["last_seen_at"] >= listing["first_seen_at"]


def test_save_listing_is_idempotent(search_client: TestClient) -> None:
    run = search_client.post("/api/search", json={"query": "x"}).json()
    listing_id = run["hits"][0]["listing"]["id"]
    saved = search_client.post(f"/api/listings/{listing_id}/save", json={"priority": 4})
    assert saved.status_code == 200
    posting = saved.json()
    assert posting["title"] == "Data Scientist"
    assert posting["source"] == "arbeitsagentur"
    assert posting["company"]["name"] == "ACME GmbH"
    assert posting["application"]["priority"] == 4

    again = search_client.post(f"/api/listings/{listing_id}/save", json={}).json()
    assert again["id"] == posting["id"]
    assert search_client.get("/api/postings").json()["total"] == 1
    assert search_client.get(f"/api/listings/{listing_id}").json()["posting_id"] == posting["id"]


def test_search_links_already_saved_posting(search_client: TestClient) -> None:
    manual = search_client.post(
        "/api/postings",
        json={
            "title": "Data Scientist",
            "url": "https://www.arbeitsagentur.de/jobsuche/jobdetail/10000-1",
        },
    ).json()
    run = search_client.post("/api/search", json={"query": "x"}).json()
    hit = next(h for h in run["hits"] if h["listing"]["external_id"] == "10000-1")
    assert hit["listing"]["posting_id"] == manual["id"]
    assert hit["is_new"] is False  # beim Anlegen entstand bereits das Listing


def test_profiles(search_client: TestClient) -> None:
    created = search_client.post(
        "/api/search/profiles",
        json={
            "name": "DS Hamburg",
            "query": "data scientist",
            "location": "Hamburg",
            "sources": ["arbeitsagentur"],
        },
    )
    assert created.status_code == 201
    pid = created.json()["id"]
    assert [p["id"] for p in search_client.get("/api/search/profiles").json()] == [pid]
    run = search_client.post(
        "/api/search", json={"query": "data scientist", "profile_id": pid}
    ).json()
    assert run["profile_id"] == pid
    assert search_client.delete(f"/api/search/profiles/{pid}").status_code == 204
    assert search_client.get("/api/search/profiles").json() == []


def test_extended_posting_filters(client: TestClient, make_posting) -> None:
    a = make_posting(title="A", remote_type="remote", location="Hamburg", salary_min=70000)
    b = make_posting(title="B", remote_type="onsite", location="Berlin", salary_max=50000)
    app_b = b["application"]["id"]
    client.patch(f"/api/applications/{app_b}", json={"follow_up_at": "2020-01-01T09:00:00+00:00"})

    def ids(**params: object) -> list[int]:
        return [i["id"] for i in client.get("/api/postings", params=params).json()["items"]]

    assert ids(remote="remote") == [a["id"]]
    assert ids(location="berl") == [b["id"]]
    assert ids(min_salary=60000) == [a["id"]]
    assert ids(follow_up_due=True) == [b["id"]]


# --- Provider-Mapping gegen aufgezeichnete Antworten ----------------------------


def test_arbeitsagentur_provider_mapping() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/pc/v6/jobs")
        assert request.headers["X-API-Key"] == "jobboerse-jobsuche"
        assert request.url.params["was"] == "python"
        assert request.url.params["wo"] == "Hamburg"
        assert request.url.params["umkreis"] == "30"
        return httpx.Response(
            200,
            json={
                "ergebnisliste": [
                    {
                        "referenznummer": "10000-1199999999-S",
                        "stellenangebotsTitel": "Python Entwickler (m/w/d)",
                        "firma": "ACME GmbH",
                        "stellenlokationen": [{"adresse": {"ort": "Hamburg", "region": "Hamburg"}}],
                        "datumErsteVeroeffentlichung": "2026-11-20",
                    },
                    {
                        "referenznummer": "10000-2",
                        "stellenangebotsTitel": "Data Engineer",
                        "externeURL": "https://karriere.example.com/job/2",
                    },
                    {"stellenangebotsTitel": "ohne Referenznummer"},
                ]
            },
        )

    provider = ArbeitsagenturProvider("jobboerse-jobsuche", transport=httpx.MockTransport(handler))
    drafts = asyncio.run(
        provider.search(SearchQuery(query="python", location="Hamburg", radius_km=30))
    )
    assert len(drafts) == 2
    d = drafts[0]
    assert d.external_id == "10000-1199999999-s"
    assert d.url == "https://www.arbeitsagentur.de/jobsuche/jobdetail/10000-1199999999-S"
    assert d.company_name == "ACME GmbH"
    assert d.location == "Hamburg, Hamburg"
    assert d.posted_at is not None and d.posted_at.year == 2026
    assert drafts[1].url == "https://karriere.example.com/job/2"
    assert drafts[1].location is None


def test_arbeitsagentur_no_hits_and_homeoffice_filter() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["homeoffice"] == "prozentual_0"
        assert "arbeitszeit" not in request.url.params
        return httpx.Response(200, json={"maxErgebnisse": 0})  # keine "ergebnisliste"

    provider = ArbeitsagenturProvider("k", transport=httpx.MockTransport(handler))
    assert asyncio.run(provider.search(SearchQuery(query="x", remote_only=True))) == []


def test_arbeitsagentur_maps_legacy_v4_fields() -> None:
    d = to_draft(
        {
            "refnr": "10000-1-S",
            "titel": "Alt",
            "arbeitgeber": "Old GmbH",
            "arbeitsort": {"ort": "Kiel"},
        }
    )
    assert d is not None
    assert (d.external_id, d.company_name, d.location) == ("10000-1-s", "Old GmbH", "Kiel")


def test_arbeitsagentur_error() -> None:
    provider = ArbeitsagenturProvider(
        "k", transport=httpx.MockTransport(lambda r: httpx.Response(403))
    )
    with pytest.raises(ProviderError, match="403"):
        asyncio.run(provider.search(SearchQuery(query="x")))


def test_adzuna_provider_mapping_and_missing_key() -> None:
    assert AdzunaProvider(None, None).unavailable_reason is not None

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["what"] == "data remote"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "id": "4711",
                        "title": "Data Analyst",
                        "company": {"display_name": "Beta"},
                        "location": {"display_name": "Berlin"},
                        "contract_time": "full_time",
                        "salary_min": 55000,
                        "salary_max": 65000,
                        "salary_is_predicted": "0",
                        "created": "2026-11-21T10:00:00Z",
                        "redirect_url": "https://www.adzuna.de/land/ad/4711",
                    },
                    {
                        "id": "4712",
                        "title": "Geschätzt",
                        "salary_min": 40000,
                        "salary_is_predicted": "1",
                    },
                ]
            },
        )

    provider = AdzunaProvider("id", "key", transport=httpx.MockTransport(handler))
    drafts = asyncio.run(provider.search(SearchQuery(query="data", remote_only=True)))
    assert drafts[0].salary_min == 55000
    assert drafts[0].employment_type == "Vollzeit"
    assert drafts[1].salary_min is None  # geschätztes Gehalt nicht übernehmen
    assert drafts[0].remote_type is RemoteType.UNKNOWN
