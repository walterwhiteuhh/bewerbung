from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from bewerbung.domain.enums import RemoteType
from bewerbung.sources.extract import extract_posting, html_to_text

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
