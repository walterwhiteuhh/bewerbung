from __future__ import annotations

import asyncio
from collections.abc import Iterator
from datetime import timedelta

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event

from bewerbung.config import Settings
from bewerbung.db.models import SearchRun
from bewerbung.db.types import utcnow
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
    assert d.location == "Hamburg"
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
            "arbeitsort": {"ort": "Kiel", "region": "SCHLESWIG-HOLSTEIN"},
        }
    )
    assert d is not None
    assert (d.external_id, d.company_name, d.location) == (
        "10000-1-s",
        "Old GmbH",
        "Kiel, Schleswig-Holstein",
    )


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


def test_work_time_filter_is_passed_and_recorded(
    search_client: TestClient, aa: FakeProvider
) -> None:
    run = search_client.post(
        "/api/search",
        json={"query": "verkauf", "work_times": ["minijob", "teilzeit"], "offer_type": "arbeit"},
    ).json()
    assert aa.queries[0].work_times == ["minijob", "teilzeit"]
    assert run["work_times"] == ["minijob", "teilzeit"]
    assert run["offer_type"] == "arbeit"
    bad = search_client.post("/api/search", json={"query": "x", "work_times": ["egal"]})
    assert bad.status_code == 422

    prof = search_client.post(
        "/api/search/profiles",
        json={"name": "Minijobs HH", "query": "verkauf", "work_times": ["minijob"]},
    ).json()
    assert prof["work_times"] == ["minijob"]


def test_arbeitsagentur_work_time_and_offer_codes() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        item = {"refnr": "1", "titel": "Aushilfe Verkauf", "arbeitgeber": "Laden"}
        return httpx.Response(200, json={"stellenangebote": [item]})

    provider = ArbeitsagenturProvider("k", transport=httpx.MockTransport(handler))
    drafts = asyncio.run(provider.search(SearchQuery(query="verkauf", work_times=["minijob"])))
    assert seen[0].url.params["arbeitszeit"] == "mj"
    assert seen[0].url.params["angebotsart"] == "1"
    assert drafts[0].employment_type == "Minijob"

    asyncio.run(
        provider.search(
            SearchQuery(query="x", work_times=["teilzeit", "schicht"], offer_type="ausbildung")
        )
    )
    assert seen[1].url.params["arbeitszeit"] == "tz;snw"
    assert seen[1].url.params["angebotsart"] == "4"


def test_adzuna_minijob_uses_part_time_and_keyword() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["what"] == "kasse minijob"
        assert request.url.params["part_time"] == "1"
        assert "full_time" not in request.url.params
        return httpx.Response(200, json={"results": []})

    provider = AdzunaProvider("id", "key", transport=httpx.MockTransport(handler))
    assert asyncio.run(provider.search(SearchQuery(query="kasse", work_times=["minijob"]))) == []


def test_arbeitsagentur_marks_minijob_and_search_keeps_known_values(
    search_client: TestClient, aa: FakeProvider
) -> None:
    d = to_draft({"refnr": "x-1", "titel": "Aushilfe", "istGeringfuegigeBeschaeftigung": True})
    assert d is not None
    assert d.employment_type == "Minijob"

    aa.drafts = [aa.drafts[0].model_copy(update={"employment_type": "Minijob"})]
    first = search_client.post("/api/search", json={"query": "x"}).json()
    listing_id = first["hits"][0]["listing"]["id"]
    # Gleiche Anzeige, diesmal ohne Arbeitszeit-Angabe, aber geändertem Inhalt
    aa.drafts = [aa.drafts[0].model_copy(update={"employment_type": None, "title": "Neu"})]
    again = search_client.post("/api/search", json={"query": "x"}).json()
    hit = next(h for h in again["hits"] if h["listing"]["id"] == listing_id)
    assert hit["listing"]["title"] == "Neu"
    assert hit["listing"]["employment_type"] == "Minijob"


def test_edit_profile_and_hide_runs(search_client: TestClient) -> None:
    pid = search_client.post("/api/search/profiles", json={"name": "Alt", "query": "data"}).json()[
        "id"
    ]
    updated = search_client.put(
        f"/api/search/profiles/{pid}",
        json={
            "name": "Minijobs HH",
            "query": "verkauf",
            "location": "Hamburg",
            "work_times": ["minijob"],
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert (body["name"], body["query"], body["work_times"]) == (
        "Minijobs HH",
        "verkauf",
        ["minijob"],
    )
    search_client.delete(f"/api/search/profiles/{pid}")
    assert (
        search_client.put(f"/api/search/profiles/{pid}", json=body | {"id": None}).status_code
        == 404
    )

    r1 = search_client.post("/api/search", json={"query": "a"}).json()["id"]
    r2 = search_client.post("/api/search", json={"query": "b"}).json()["id"]
    assert search_client.delete(f"/api/search/runs/{r1}").status_code == 204
    assert [r["id"] for r in search_client.get("/api/search/runs").json()] == [r2]
    # Ausgeblendete Läufe bleiben abrufbar (Treffer-Historie für Auswertungen)
    assert search_client.get(f"/api/search/runs/{r1}").status_code == 200
    assert search_client.delete("/api/search/runs").json() == {"hidden": 1}
    assert search_client.get("/api/search/runs").json() == []


def test_missing_keys_only_reported_when_source_chosen(
    settings: Settings, aa: FakeProvider
) -> None:
    nokey = FakeProvider(JobSource.JOOBLE, [], unavailable="API-Key fehlt")
    with TestClient(create_app(settings, search_providers=[aa, nokey])) as c:
        assert c.post("/api/search", json={"query": "x"}).json()["errors"] == []
        chosen = c.post("/api/search", json={"query": "x", "sources": ["jooble"]}).json()
        assert chosen["errors"] == [{"source": "jooble", "message": "API-Key fehlt"}]


def _backdate(client: TestClient, run_id: int, days: int) -> None:
    factory = client.app.state.session_factory  # type: ignore[attr-defined]
    with factory() as s, s.begin():
        s.get(SearchRun, run_id).started_at = utcnow() - timedelta(days=days)  # type: ignore[union-attr]


def test_run_history_filter_and_partial_clear(search_client: TestClient) -> None:
    old = search_client.post("/api/search", json={"query": "alt", "location": "Kiel"}).json()["id"]
    mid = search_client.post("/api/search", json={"query": "mitte"}).json()["id"]
    new = search_client.post("/api/search", json={"query": "neu"}).json()["id"]
    _backdate(search_client, old, 40)
    _backdate(search_client, mid, 10)

    ids = lambda **p: [r["id"] for r in search_client.get("/api/search/runs", params=p).json()]  # noqa: E731
    assert ids() == [new, mid, old]  # nach Datum, neueste zuerst
    assert ids(q="kiel") == [old]  # Text sucht auch im Ort
    week_ago = (utcnow() - timedelta(days=14)).isoformat()
    assert ids(**{"from": week_ago}) == [new, mid]
    assert ids(to=week_ago) == [old]

    # Teilweise löschen: nur einzelne IDs, dann alles vor einem Datum
    assert search_client.delete("/api/search/runs", params={"ids": [mid, new]}).json() == {
        "hidden": 2
    }
    assert ids() == [old]
    # Komplett, die Läufe bleiben in der DB (Historie für Auswertungen)
    assert search_client.delete("/api/search/runs", params={"to": week_ago}).json() == {"hidden": 1}
    assert ids() == []
    assert search_client.get(f"/api/search/runs/{old}").status_code == 200
    # Bereits ausgeblendete werden nicht doppelt gezählt
    assert search_client.delete("/api/search/runs").json() == {"hidden": 0}


def test_search_persist_uses_constant_number_of_queries(settings: Settings) -> None:
    """Treffer werden gesammelt vorgeladen: die Zahl der SELECTs hängt nicht von der Trefferzahl ab."""
    drafts = [
        draft(JobSource.ARBEITSAGENTUR, f"1-{i}", f"Job {i}", company_name=f"Firma {i % 7}")
        for i in range(60)
    ]
    prov = FakeProvider(JobSource.ARBEITSAGENTUR, drafts)
    with TestClient(create_app(settings, search_providers=[prov])) as c:
        engine = c.app.state.session_factory.kw["bind"]  # type: ignore[attr-defined]
        selects: list[str] = []

        @event.listens_for(engine, "before_cursor_execute")
        def _count(_c, _cur, statement, *_a):  # type: ignore[no-untyped-def]
            if statement.lstrip().upper().startswith("SELECT"):
                selects.append(statement)

        first = c.post("/api/search", json={"query": "x"}).json()
        assert (first["total_hits"], first["new_hits"]) == (60, 60)
        n_first = len(selects)
        selects.clear()
        second = c.post("/api/search", json={"query": "x"}).json()
        assert (second["total_hits"], second["new_hits"]) == (60, 0)
        # Antwort inkl. Merkmale mitgezählt; mit 60 statt 6 Treffern käme ein Vielfaches
        assert n_first < 60, n_first
        assert len(selects) < 60, len(selects)


def test_hits_carry_hashtags(search_client: TestClient) -> None:
    """Treffer zeigen Vorschläge; nach dem Merken die echten Hashtags der Stelle."""
    run = search_client.post("/api/search", json={"query": "data"}).json()
    hit = next(h for h in run["hits"] if h["listing"]["title"] == "Data Scientist")
    assert "data-science" in hit["tags"]
    search_client.post(f"/api/listings/{hit['listing']['id']}/save", json={})
    again = search_client.get(f"/api/search/runs/{run['id']}").json()
    saved = next(h for h in again["hits"] if h["listing"]["id"] == hit["listing"]["id"])
    assert "data-science" in saved["tags"]  # jetzt als echter Hashtag der Stelle
