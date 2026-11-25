from __future__ import annotations

import asyncio
import json

import httpx

from bewerbung.config import Settings
from bewerbung.domain.enums import JobSource, RemoteType
from bewerbung.search.arbeitnow import ArbeitnowProvider
from bewerbung.search.base import SearchQuery
from bewerbung.search.jooble import JoobleProvider
from bewerbung.search.providers import build_providers
from bewerbung.search.remotive import RemotiveProvider


def run(provider, **q):  # type: ignore[no-untyped-def]
    return asyncio.run(provider.search(SearchQuery(**q)))


def test_registry_contains_new_sources() -> None:
    sources = [p.source for p in build_providers(Settings(database_url="sqlite://"))]
    assert {JobSource.JOOBLE, JobSource.ARBEITNOW, JobSource.REMOTIVE} <= set(sources)


def test_jooble_request_and_mapping() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(
            200,
            json={
                "totalCount": 1,
                "jobs": [
                    {
                        "title": "Aushilfe <b>Verkauf</b>",
                        "location": "Hamburg",
                        "snippet": "&nbsp;Wir suchen <b>dich</b>",
                        "type": "Part-time",
                        "link": "https://jooble.org/desc/123",
                        "company": "Laden GmbH",
                        "updated": "2026-11-24T09:00:00.0000000",
                        "id": 123,
                    },
                    {"title": "ohne Link"},
                ],
            },
        )

    provider = JoobleProvider("secret", transport=httpx.MockTransport(handler))
    drafts = run(
        provider, query="verkauf", location="Hamburg", radius_km=25, work_times=["minijob"]
    )
    assert len(drafts) == 1
    d = drafts[0]
    assert (d.title, d.company_name, d.employment_type) == (
        "Aushilfe Verkauf",
        "Laden GmbH",
        "Teilzeit",
    )
    assert d.description == "Wir suchen dich"
    assert d.posted_at is not None
    req = seen[0]
    assert req.url.path == "/api/secret"
    body = json.loads(req.content)
    assert body == {
        "keywords": "verkauf minijob",
        "location": "Hamburg",
        "page": "1",
        "ResultOnPage": "50",
        "radius": "25",
    }
    assert JoobleProvider(None).unavailable_reason


ARBEITNOW_PAGE = {
    "data": [
        {
            "slug": "data-scientist-acme-1",
            "title": "Data Scientist (m/w/d)",
            "company_name": "ACME",
            "location": "Hamburg",
            "remote": False,
            "tags": ["Python", "Machine Learning"],
            "job_types": ["full time"],
            "description": "<p>Python und SQL</p>",
            "url": "https://www.arbeitnow.com/jobs/acme/data-scientist-acme-1",
            "created_at": 1764000000,
        },
        {
            "slug": "minijob-kasse-2",
            "title": "Minijob Kasse",
            "company_name": "Markt",
            "location": "Berlin",
            "remote": False,
            "tags": [],
            "job_types": [],
            "description": "Kasse",
            "url": "https://www.arbeitnow.com/jobs/markt/minijob-kasse-2",
            "created_at": 1764000000,
        },
        {
            "slug": "remote-python-3",
            "title": "Python Developer",
            "company_name": "Remote Co",
            "location": "Munich",
            "remote": True,
            "tags": ["Python"],
            "job_types": ["full time"],
            "description": "Remote",
            "url": "https://www.arbeitnow.com/jobs/remote/remote-python-3",
            "created_at": 1764000000,
        },
    ]
}


def _arbeitnow() -> ArbeitnowProvider:
    calls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.params["page"])
        return httpx.Response(
            200, json=ARBEITNOW_PAGE if request.url.params["page"] == "1" else {"data": []}
        )

    return ArbeitnowProvider(transport=httpx.MockTransport(handler))


def test_arbeitnow_filters_locally() -> None:
    hits = run(_arbeitnow(), query="python", location="Hamburg")
    # Hamburg vor Ort + Remote-Stelle (Ort egal), aber nicht die Kasse in Berlin
    assert [d.external_id for d in hits] == ["data-scientist-acme-1", "remote-python-3"]
    assert hits[0].description == "Python und SQL"
    assert hits[1].remote_type is RemoteType.REMOTE

    assert [d.external_id for d in run(_arbeitnow(), query="python", remote_only=True)] == [
        "remote-python-3"
    ]
    mini = run(_arbeitnow(), query="kasse", work_times=["minijob"])
    assert [d.external_id for d in mini] == ["minijob-kasse-2"]
    assert mini[0].employment_type == "Minijob"


def test_remotive_keeps_only_reachable_regions() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["search"] == "python"
        return httpx.Response(
            200,
            json={
                "jobs": [
                    {
                        "id": 1,
                        "title": "Backend (EU)",
                        "tags": ["Python"],
                        "candidate_required_location": "Europe",
                        "job_type": "full_time",
                        "url": "https://remotive.com/1",
                        "company_name": "A",
                        "publication_date": "2026-11-20T10:00:00",
                    },
                    {
                        "id": 2,
                        "title": "US only",
                        "candidate_required_location": "USA Only",
                        "job_type": "full_time",
                        "url": "https://remotive.com/2",
                    },
                    {
                        "id": 3,
                        "title": "Part time anywhere (Python)",
                        "candidate_required_location": "Worldwide",
                        "job_type": "part_time",
                        "url": "https://remotive.com/3",
                    },
                    {
                        "id": 4,
                        "title": "Office Assistant",
                        "candidate_required_location": "Worldwide",
                        "job_type": "full_time",
                        "description": "Passt nicht zum Suchbegriff",
                    },
                ]
            },
        )

    provider = RemotiveProvider(transport=httpx.MockTransport(handler))
    hits = run(provider, query="python")
    assert [d.external_id for d in hits] == ["1", "3"]
    assert hits[0].location == "Remote (Europe)"
    assert hits[0].employment_type == "Vollzeit"
    assert [d.external_id for d in run(provider, query="python", work_times=["teilzeit"])] == ["3"]
    assert run(provider, query="python", offer_type="ausbildung") == []
