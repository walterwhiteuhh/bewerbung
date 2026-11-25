from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import httpx
import pytest
from alembic import command
from fastapi.testclient import TestClient

from bewerbung.config import Settings
from bewerbung.db.migrate import alembic_config
from bewerbung.domain.logos import clean_logo_url, logo_from_payload
from bewerbung.main import create_app
from bewerbung.search.aa_logos import AaLogoCache
from bewerbung.search.arbeitsagentur import to_draft
from bewerbung.search.remotive import to_draft as remotive_draft
from bewerbung.sources.extract import extract_posting

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("https://cdn.example/logo.png", "https://cdn.example/logo.png"),
        ({"@type": "ImageObject", "url": "https://x.de/l.jpg"}, "https://x.de/l.jpg"),
        ("//static.example/l.svg", "https://static.example/l.svg"),
        (["", "https://x.de/a.png"], "https://x.de/a.png"),
        ("data:image/png;base64,AAAA", None),
        ("javascript:alert(1)", None),
        ("/relative/logo.png", None),
        (None, None),
    ],
)
def test_clean_logo_url(value: object, expected: str | None) -> None:
    assert clean_logo_url(value) == expected


def test_logo_from_payload_variants() -> None:
    ld = {"hiringOrganization": {"name": "ACME", "logo": "https://acme.de/logo.png"}}
    assert logo_from_payload({"json_ld": ld}) == "https://acme.de/logo.png"
    assert logo_from_payload(ld) == "https://acme.de/logo.png"
    assert logo_from_payload({"company_logo": "https://r.io/c.png"}) == "https://r.io/c.png"
    saved = {"listing_id": 3, "source_payload": {"company_logo": "https://r.io/c.png"}}
    assert logo_from_payload(saved) == "https://r.io/c.png"
    aa = {"referenznummer": "10000-1", "kundennummerHash": "abc_DEF-123="}
    assert logo_from_payload(aa) == "/api/logos/arbeitsagentur/abc_DEF-123%3D"
    assert logo_from_payload({"referenznummer": "1"}) is None
    assert logo_from_payload(None) is None


def test_providers_and_extractor_set_logo() -> None:
    aa = to_draft(
        {"referenznummer": "10000-1", "stellenangebotsTitel": "Koch", "kundennummerHash": "h4sh42"}
    )
    assert aa is not None and aa.company_logo_url == "/api/logos/arbeitsagentur/h4sh42"
    rem = remotive_draft({"id": 7, "title": "Dev", "company_logo": "https://r.io/x.png"})
    assert rem is not None and rem.company_logo_url == "https://r.io/x.png"
    html = (
        '<script type="application/ld+json">{"@type":"JobPosting","title":"Dev",'
        '"hiringOrganization":{"@type":"Organization","name":"ACME",'
        '"logo":{"@type":"ImageObject","url":"https://acme.de/l.png"}}}</script>'
    )
    assert extract_posting(html).company_logo_url == "https://acme.de/l.png"


def test_posting_company_gets_logo(client: TestClient) -> None:
    posting = client.post(
        "/api/postings",
        json={
            "title": "Dev",
            "company_name": "ACME GmbH",
            "raw_payload": {"json_ld": {"hiringOrganization": {"logo": "https://acme.de/l.png"}}},
        },
    ).json()
    assert posting["company"]["logo_url"] == "https://acme.de/l.png"
    # Zweite Stelle derselben Firma ohne Logo: Firmenlogo bleibt erhalten.
    other = client.post("/api/postings", json={"title": "Ops", "company_name": "ACME"}).json()
    assert other["company"]["logo_url"] == "https://acme.de/l.png"
    listed = client.get("/api/postings").json()["items"]
    assert {p["company"]["logo_url"] for p in listed} == {"https://acme.de/l.png"}


def _fake_logos(tmp_path: Path, status: int = 200, body: bytes = PNG) -> tuple[AaLogoCache, list]:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(status, content=body)

    return AaLogoCache(tmp_path / "logos", "key", transport=httpx.MockTransport(handler)), calls


def test_aa_logo_cache(tmp_path: Path) -> None:
    cache, calls = _fake_logos(tmp_path)
    first = asyncio.run(cache.get("h4sh42"))
    second = asyncio.run(cache.get("h4sh42"))
    assert first is not None and first.media_type == "image/png"
    assert second == first
    assert len(calls) == 1
    assert calls[0].headers["X-API-Key"] == "key"
    assert asyncio.run(cache.get("../etc")) is None  # ungültiger Hash, kein Request
    assert len(calls) == 1


def test_aa_logo_missing_and_non_image(tmp_path: Path) -> None:
    cache, calls = _fake_logos(tmp_path, status=404)
    assert asyncio.run(cache.get("nologo1")) is None
    assert asyncio.run(cache.get("nologo1")) is None
    assert len(calls) == 1  # 404 wird eine Woche lang gemerkt

    svg, _ = _fake_logos(tmp_path / "svg", body=b"<svg onload=alert(1)>")
    assert asyncio.run(svg.get("svglogo")) is None


def test_aa_logo_endpoint(settings: Settings, tmp_path: Path) -> None:
    cache, _ = _fake_logos(tmp_path)
    with TestClient(create_app(settings, aa_logos=cache)) as c:
        ok = c.get("/api/logos/arbeitsagentur/h4sh42")
        assert ok.status_code == 200
        assert ok.headers["content-type"] == "image/png"
        assert "max-age" in ok.headers["cache-control"]
        assert c.get("/api/logos/arbeitsagentur/x").status_code == 404


def test_migration_backfills_logos(tmp_path: Path) -> None:
    db = tmp_path / "m.db"
    cfg = alembic_config(f"sqlite:///{db.as_posix()}")
    command.upgrade(cfg, "0007")
    con = sqlite3.connect(db)
    now = "2026-11-25 00:00:00.000000"
    con.execute(
        "INSERT INTO companies (id, name, name_key, created_at, updated_at)"
        " VALUES (1, 'ACME', 'acme', ?, ?)",
        (now, now),
    )
    payload = json.dumps({"json_ld": {"hiringOrganization": {"logo": "https://acme.de/l.png"}}})
    con.execute(
        "INSERT INTO job_postings (id, company_id, title, remote_type, salary_currency, source,"
        " raw_payload, created_at, updated_at) VALUES (1, 1, 'Dev', 'unknown', 'EUR', 'stepstone',"
        " ?, ?, ?)",
        (payload, now, now),
    )
    con.execute(
        "INSERT INTO listings (id, source, external_id, title, remote_type, raw_payload,"
        " first_seen_at, last_seen_at, created_at, updated_at)"
        " VALUES (1, 'remotive', '7', 'Dev', 'remote', ?, ?, ?, ?, ?)",
        (json.dumps({"company_logo": "https://r.io/x.png"}), now, now, now, now),
    )
    con.commit()
    con.close()

    command.upgrade(cfg, "head")
    con = sqlite3.connect(db)
    assert con.execute("SELECT logo_url FROM companies").fetchone() == ("https://acme.de/l.png",)
    assert con.execute("SELECT company_logo_url FROM listings").fetchone() == (
        "https://r.io/x.png",
    )
    con.close()
