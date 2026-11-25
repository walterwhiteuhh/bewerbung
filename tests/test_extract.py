from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from bewerbung.domain.enums import RemoteType
from bewerbung.sources.extract import extract_posting, html_to_text, looks_like_challenge

FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def test_jsonld_job_posting() -> None:
    result = extract_posting(load("stepstone_jsonld.html"))
    assert result.method == "json-ld"
    assert result.title == "Data Scientist (m/w/d)"
    assert result.company_name == "ACME Analytics GmbH"
    assert result.location == "Hamburg, Berlin"
    assert result.remote_type is RemoteType.HYBRID  # Telearbeit + Standort
    assert result.employment_type == "Vollzeit, Teilzeit"
    assert (result.salary_min, result.salary_max, result.salary_currency) == (60000, 78000, "EUR")
    assert result.posted_at == datetime(2026, 11, 20, tzinfo=UTC)
    assert result.description == "Wir suchen dich!\n\n• Python & SQL\n• Machine Learning"
    assert result.raw["json_ld"]["@type"] == "JobPosting"


def test_jsonld_in_graph_with_plain_strings() -> None:
    result = extract_posting(load("graph_jsonld.html"))
    assert result.title == "Backend Engineer"
    assert result.company_name == "Beispiel AG"
    assert result.location == "München"
    assert result.remote_type is RemoteType.UNKNOWN
    assert (result.salary_min, result.salary_max, result.salary_currency) == (70000, 70000, "EUR")
    assert result.posted_at == datetime(2026, 11, 1, 7, 30, tzinfo=UTC)


def test_opengraph_fallback_and_broken_jsonld() -> None:
    result = extract_posting(load("opengraph_only.html"))
    assert result.method == "opengraph"
    assert result.title == "Senior Python Developer – Firma X"
    assert result.company_name is None
    assert result.description == "Remote möglich. 30 Tage Urlaub."


def test_page_without_data() -> None:
    result = extract_posting("<html><body>nichts</body></html>")
    assert result.method == "none"
    assert result.is_empty


@pytest.mark.parametrize(
    ("html", "expected"),
    [
        ("<p>A</p><p>B</p>", "A\n\nB"),
        ("Zeile<br>zwei", "Zeile\nzwei"),
        ("<ul><li>x</li><li>y</li></ul>", "• x\n• y"),
    ],
)
def test_html_to_text(html: str, expected: str) -> None:
    assert html_to_text(html) == expected


def _jsonld(node: dict) -> str:
    return (
        f'<script type="application/ld+json">{json.dumps({"@type": "JobPosting", **node})}</script>'
    )


def test_real_world_quirks() -> None:
    result = extract_posting(
        _jsonld(
            {
                "title": "Engineer",
                "description": "null<p>Wir suchen</p>",
                "employmentType": "Full-Time",
                "jobLocation": {"address": {"addressLocality": "DEU - Berlin"}},
                "baseSalary": {
                    "currency": "EUR",
                    "value": {"minValue": 0, "maxValue": 0, "unitText": "YEAR"},
                },
            }
        )
    )
    assert result.description == "Wir suchen"
    assert result.employment_type == "Vollzeit"
    assert result.location == "Berlin"
    assert (result.salary_min, result.salary_max, result.salary_currency) == (None, None, None)


def test_remote_from_location_text() -> None:
    result = extract_posting(_jsonld({"title": "Dev", "jobLocation": {"address": "100% Remote"}}))
    assert result.remote_type is RemoteType.REMOTE


def test_challenge_page_detected() -> None:
    html = "<html><head><title>Ihr Browser wird geprüft – reCAPTCHA</title></head></html>"
    assert looks_like_challenge(html, extract_posting(html))
    ok = load("stepstone_jsonld.html")
    assert not looks_like_challenge(ok, extract_posting(ok))
