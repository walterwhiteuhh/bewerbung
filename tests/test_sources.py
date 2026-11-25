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


@pytest.mark.parametrize(
    ("url", "source", "external_id"),
    [
        ("https://www.xing.com/jobs/hamburg-data-scientist-123456789?ijt=x", "xing", "123456789"),
        (
            "https://de.indeed.com/viewjob?jk=1a2b3c4d5e6f7a8b&from=serp",
            "indeed",
            "1a2b3c4d5e6f7a8b",
        ),
        ("https://de.indeed.com/jobs?q=python&vjk=1a2b3c4d5e6f7a8b", "indeed", "1a2b3c4d5e6f7a8b"),
        (
            "https://www.arbeitsagentur.de/jobsuche/jobdetail/10000-1199999999-S",
            "arbeitsagentur",
            "10000-1199999999-s",
        ),
        (
            "https://www.glassdoor.de/job-listing/data-scientist-acme-JV_IC123_KO0,14_KE15,19.htm?jl=1009876543210",
            "glassdoor",
            "1009876543210",
        ),
        (
            "https://acme.jobs.personio.de/job/1234567?language=de&display=en",
            "personio",
            "acme/1234567",
        ),
        ("https://boards.greenhouse.io/acme/jobs/4567890", "greenhouse", "acme/4567890"),
        (
            "https://job-boards.greenhouse.io/acme/jobs/4567890?gh_src=x",
            "greenhouse",
            "acme/4567890",
        ),
        (
            "https://jobs.lever.co/acme/0b1c2d3e-4f50-6172-8394-a5b6c7d8e9f0/apply",
            "lever",
            "acme/0b1c2d3e-4f50-6172-8394-a5b6c7d8e9f0",
        ),
        (
            "https://acme.softgarden.io/job/45678901/Data-Engineer-m-w-d-?jobDbPVId=1",
            "softgarden",
            "acme/45678901",
        ),
        ("https://join.com/companies/acme/12345678-backend-engineer", "join", "acme/12345678"),
        (
            "https://acme.wd3.myworkdayjobs.com/en-US/External/job/Berlin/Senior-Engineer_R-12345?source=li",
            "workday",
            "acme/r-12345",
        ),
    ],
)
def test_platform_urls(url: str, source: str, external_id: str) -> None:
    ref = default_registry().identify(url)
    assert ref.source == source
    assert ref.external_id == external_id


def test_greenhouse_hosts_normalize_to_same_url() -> None:
    reg = default_registry()
    a = reg.identify("https://boards.greenhouse.io/acme/jobs/4567890")
    b = reg.identify("https://job-boards.greenhouse.io/acme/jobs/4567890?gh_src=x")
    assert a.url_normalized == b.url_normalized


def test_indeed_keeps_only_job_key() -> None:
    ref = default_registry().identify(
        "https://de.indeed.com/viewjob?jk=abc123def4567890&from=serp&tk=xyz"
    )
    assert ref.url_normalized == "https://de.indeed.com/viewjob?jk=abc123def4567890"
