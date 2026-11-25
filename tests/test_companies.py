from __future__ import annotations

import asyncio
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from bewerbung.config import Settings
from bewerbung.domain.websites import normalize_website, website_from_payload
from bewerbung.main import create_app
from bewerbung.sources.fetcher import FetchError
from bewerbung.sources.site_logo import LogoStore, SiteLogoFetcher, icon_candidates, sniff_image

PNG = b"\x89PNG\r\n\x1a\n" + b"\x01" * 40
ICO = b"\x00\x00\x01\x00" + b"\x02" * 40


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("acme.de", "https://acme.de"),
        ("https://www.ACME.de/", "https://www.acme.de"),
        ("http://acme.de/karriere/", "http://acme.de/karriere"),
        ("localhost", None),
        ("ftp://acme.de", None),
        ("", None),
    ],
)
def test_normalize_website(value: str, expected: str | None) -> None:
    assert normalize_website(value) == expected


def test_website_from_payload_skips_portals() -> None:
    org = {"name": "ACME", "sameAs": "https://www.acme.de", "url": "https://acme.personio.de"}
    assert website_from_payload({"json_ld": {"hiringOrganization": org}}) == "https://www.acme.de"
    portal_only = {"hiringOrganization": {"url": "https://www.stepstone.de/cmp/acme"}}
    assert website_from_payload(portal_only) is None


def test_icon_candidates_ranking() -> None:
    html = """<head>
      <link rel="icon" href="/favicon-16.png" sizes="16x16">
      <link rel="icon" href="/favicon-32.png" sizes="32x32">
      <link rel="icon" type="image/svg+xml" href="/logo.svg">
      <link rel="apple-touch-icon" href="/touch.png" sizes="180x180">
      <link rel="icon" href="data:image/png;base64,AAAA">
    </head>"""
    assert icon_candidates(html, "https://acme.de/start") == [
        "https://acme.de/touch.png",
        "https://acme.de/logo.svg",
        "https://acme.de/favicon-32.png",
        "https://acme.de/favicon-16.png",
        "https://acme.de/apple-touch-icon.png",
        "https://acme.de/favicon.ico",
    ]


def test_sniff_image() -> None:
    assert sniff_image(PNG) == "png"
    assert sniff_image(ICO) == "ico"
    assert sniff_image(b'<?xml version="1.0"?><svg xmlns="x"></svg>') == "svg"
    assert sniff_image(b"<html>nope</html>") is None


def _site(routes: dict[str, httpx.Response]) -> SiteLogoFetcher:
    def handler(request: httpx.Request) -> httpx.Response:
        return routes.get(str(request.url), httpx.Response(404))

    return SiteLogoFetcher(check_host=False, transport=httpx.MockTransport(handler))


def test_site_logo_follows_redirect_and_falls_back() -> None:
    fetcher = _site(
        {
            "https://acme.de": httpx.Response(301, headers={"location": "https://www.acme.de/"}),
            "https://www.acme.de/": httpx.Response(
                200, text='<link rel="apple-touch-icon" href="/broken.png">'
            ),
            "https://www.acme.de/broken.png": httpx.Response(200, text="<html>kein Bild</html>"),
            "https://www.acme.de/favicon.ico": httpx.Response(200, content=ICO),
        }
    )
    assert asyncio.run(fetcher.fetch_logo("https://acme.de")) == ICO

    with pytest.raises(FetchError):
        asyncio.run(_site({}).fetch_logo("https://leer.de"))


def test_logo_store_is_content_addressed(tmp_path: Path) -> None:
    store = LogoStore(tmp_path)
    a, b = store.save(PNG), store.save(PNG)
    assert a == b and a.media_type == "image/png"
    assert store.path(a.name) is not None
    assert store.path("../x.png") is None
    with pytest.raises(ValueError, match="Bildformat"):
        store.save(b"nope")


@pytest.fixture
def site_client(settings: Settings) -> TestClient:
    fetcher = _site(
        {
            "https://acme.de": httpx.Response(200, text='<link rel="icon" href="/l.png">'),
            "https://acme.de/l.png": httpx.Response(200, content=PNG),
        }
    )
    return TestClient(create_app(settings, site_logos=fetcher))


def test_company_crud_and_website_logo(site_client: TestClient) -> None:
    with site_client as c:
        posting = c.post("/api/postings", json={"title": "Dev", "company_name": "ACME GmbH"}).json()
        cid = posting["company"]["id"]

        assert c.post(f"/api/companies/{cid}/logo").status_code == 400  # keine Website

        bad = c.patch(f"/api/companies/{cid}", json={"website": "kein url"})
        assert bad.status_code == 400
        upd = c.patch(
            f"/api/companies/{cid}",
            json={"website": "acme.de", "industry": "Logistik", "location": "Hamburg"},
        ).json()
        assert upd["website"] == "https://acme.de"
        assert upd["industry"] == "Logistik"

        logo = c.post(f"/api/companies/{cid}/logo")
        assert logo.status_code == 200, logo.text
        body = logo.json()
        assert body["logo_source"] == "website"
        assert body["logo_url"].startswith("/api/logos/files/")

        img = c.get(body["logo_url"])
        assert img.status_code == 200
        assert img.headers["content-type"] == "image/png"
        assert "sandbox" in img.headers["content-security-policy"]
        assert c.get("/api/logos/files/abc.png").status_code == 404

        detail = c.get(f"/api/postings/{posting['id']}").json()
        assert detail["company"]["logo_url"] == body["logo_url"]
        assert detail["company"]["website"] == "https://acme.de"

        listed = c.get("/api/companies").json()
        assert listed[0]["posting_count"] == 1

        cleared = c.patch(f"/api/companies/{cid}", json={"logo_url": None}).json()
        assert cleared["logo_url"] is None and cleared["logo_source"] is None


def test_company_rename_conflict(client: TestClient) -> None:
    a = client.post("/api/postings", json={"title": "A", "company_name": "ACME"}).json()
    client.post("/api/postings", json={"title": "B", "company_name": "Beta AG"})
    resp = client.patch(f"/api/companies/{a['company']['id']}", json={"name": "Beta"})
    assert resp.status_code == 400


def test_import_sets_company_website(client: TestClient) -> None:
    payload = {"json_ld": {"hiringOrganization": {"name": "ACME", "sameAs": "https://acme.de"}}}
    posting = client.post(
        "/api/postings", json={"title": "Dev", "company_name": "ACME", "raw_payload": payload}
    ).json()
    assert posting["company"]["website"] == "https://acme.de"
