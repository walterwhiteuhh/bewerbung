from __future__ import annotations

import pytest

from bewerbung.domain.enums import JobSource
from bewerbung.sources import default_registry


@pytest.mark.parametrize(
    ("url", "external_id"),
    [
        ("https://www.linkedin.com/jobs/view/3912345678/", "3912345678"),
        (
            "https://de.linkedin.com/jobs/view/senior-data-scientist-at-acme-3912345678?trk=abc",
            "3912345678",
        ),
        (
            "https://www.linkedin.com/jobs/search/?currentJobId=3912345678&keywords=python",
            "3912345678",
        ),
        ("linkedin.com/jobs/view/3912345678", "3912345678"),
    ],
)
def test_linkedin_urls(url: str, external_id: str) -> None:
    ref = default_registry().identify(url)
    assert ref.source is JobSource.LINKEDIN
    assert ref.external_id == external_id
    assert ref.url_normalized == f"https://linkedin.com/jobs/view/{external_id}"


@pytest.mark.parametrize(
    "url",
    [
        "https://www.stepstone.de/stellenangebote--Data-Scientist-m-w-d-Hamburg-ACME-GmbH--12345678-inline.html",
        "https://www.stepstone.de/stellenangebote--Data-Scientist-m-w-d-Hamburg-ACME-GmbH--12345678-inline.html?rltr=1_1&cid=foo#top",
    ],
)
def test_stepstone_urls(url: str) -> None:
    ref = default_registry().identify(url)
    assert ref.source is JobSource.STEPSTONE
    assert ref.external_id == "12345678"
    assert "?" not in ref.url_normalized and "#" not in ref.url_normalized


def test_generic_url_strips_tracking() -> None:
    ref = default_registry().identify(
        "https://Jobs.Example.com/stelle/42/?utm_source=x&lang=de#apply"
    )
    assert ref.source is JobSource.OTHER
    assert ref.external_id is None
    assert ref.url_normalized == "https://jobs.example.com/stelle/42?lang=de"


def test_lookalike_domain_is_not_linkedin() -> None:
    assert (
        default_registry().identify("https://notlinkedin.com/jobs/view/3912345678").source
        is JobSource.OTHER
    )


def test_invalid_url() -> None:
    with pytest.raises(ValueError, match="Ungültige URL"):
        default_registry().identify("https://")
