"""Konkrete Adapter. Reine URL-Logik, damit sie schnell und ohne Netzwerk testbar sind."""

from __future__ import annotations

import re
from urllib.parse import SplitResult, parse_qs

from bewerbung.domain.enums import JobSource
from bewerbung.sources.base import SourceAdapter, SourceReference, strip_tracking


def _host(parts: SplitResult) -> str:
    return (parts.hostname or "").lower()


def _host_matches(host: str, *domains: str) -> bool:
    return any(host == d or host.endswith(f".{d}") for d in domains)


class LinkedInAdapter(SourceAdapter):
    """Erkennt ``/jobs/view/<id>``, ``/jobs/view/<slug>-<id>`` und ``?currentJobId=<id>``."""

    source = JobSource.LINKEDIN
    _VIEW = re.compile(r"/jobs/view/(?:[^/]*?-)?(\d{6,})")

    def matches(self, parts: SplitResult) -> bool:
        host = _host(parts)
        return host == "linkedin.com" or host.endswith(".linkedin.com")

    def identify(self, parts: SplitResult) -> SourceReference:
        job_id: str | None = None
        if m := self._VIEW.search(parts.path):
            job_id = m.group(1)
        else:
            qs = parse_qs(parts.query)
            candidates = qs.get("currentJobId") or qs.get("jobId") or []
            job_id = next((c for c in candidates if c.isdigit()), None)

        if job_id:
            return SourceReference(
                source=self.source,
                external_id=job_id,
                url_normalized=f"https://linkedin.com/jobs/view/{job_id}",
            )
        return SourceReference(source=self.source, url_normalized=strip_tracking(parts))

    def fetch_url(self, reference: SourceReference, original_url: str) -> str:
        # Such-URLs (?currentJobId=) liefern keine Stellendaten, die Detailseite schon.
        if reference.external_id:
            return f"https://www.linkedin.com/jobs/view/{reference.external_id}/"
        return original_url


class StepstoneAdapter(SourceAdapter):
    """Erkennt ``/stellenangebote--<slug>--<id>-inline.html`` (de/at/ch/...)."""

    source = JobSource.STEPSTONE
    _ID = re.compile(r"--(\d{5,})(?:-inline)?\.html$")

    def matches(self, parts: SplitResult) -> bool:
        host = _host(parts)
        return re.search(r"(^|\.)stepstone\.[a-z.]+$", host) is not None

    def identify(self, parts: SplitResult) -> SourceReference:
        normalized = strip_tracking(parts._replace(query=""))
        if m := self._ID.search(parts.path):
            return SourceReference(
                source=self.source, external_id=m.group(1), url_normalized=normalized
            )
        return SourceReference(source=self.source, url_normalized=normalized)


class PatternAdapter(SourceAdapter):
    """Datengetriebener Adapter: Host-Domains + Regex auf Pfad bzw. Query-Parameter.

    Die meisten Portale kodieren die Job-ID stabil in der URL; ein Muster pro Portal
    reicht. ``external_id`` kann mit dem Mandanten präfixiert werden (``firma/123``),
    weil Bewerbermanagement-Systeme IDs nur pro Firma eindeutig vergeben.
    """

    def __init__(
        self,
        source: JobSource,
        domains: tuple[str, ...],
        *,
        path: str | None = None,
        query: tuple[str, ...] = (),
        tenant_from_host: bool = False,
        keep_query: tuple[str, ...] = (),
    ) -> None:
        self.source = source
        self._domains = domains
        self._path = re.compile(path) if path else None
        self._query = query
        self._tenant_from_host = tenant_from_host
        self._keep_query = keep_query

    def matches(self, parts: SplitResult) -> bool:
        return _host_matches(_host(parts), *self._domains)

    def _job_id(self, parts: SplitResult) -> str | None:
        if self._path and (m := self._path.search(parts.path)):
            groups = [g for g in m.groups() if g]
            return "/".join(groups) if groups else None
        qs = parse_qs(parts.query)
        return next((qs[k][0] for k in self._query if qs.get(k)), None)

    def identify(self, parts: SplitResult) -> SourceReference:
        job_id = self._job_id(parts)
        if job_id and self._tenant_from_host:
            job_id = f"{_host(parts).split('.')[0]}/{job_id}"
        qs = parse_qs(parts.query)
        kept = "&".join(f"{k}={qs[k][0]}" for k in self._keep_query if qs.get(k))
        normalized = strip_tracking(parts._replace(query=kept))
        return SourceReference(
            source=self.source,
            external_id=job_id.lower() if job_id else None,
            url_normalized=normalized,
        )


class GreenhouseAdapter(PatternAdapter):
    """``boards.``/``job-boards.greenhouse.io`` sind dieselbe Stelle: eine URL daraus machen."""

    def __init__(self) -> None:
        super().__init__(JobSource.GREENHOUSE, ("greenhouse.io",), path=r"^/([^/]+)/jobs/(\d+)")

    def identify(self, parts: SplitResult) -> SourceReference:
        ref = super().identify(parts)
        if ref.external_id:
            company, job = ref.external_id.split("/")
            url = f"https://boards.greenhouse.io/{company}/jobs/{job}"
            return ref.model_copy(update={"url_normalized": url})
        return ref


def platform_adapters() -> list[SourceAdapter]:
    """Alle bekannten Portale. Reihenfolge egal, Domains überschneiden sich nicht."""
    return [
        LinkedInAdapter(),
        StepstoneAdapter(),
        PatternAdapter(JobSource.XING, ("xing.com",), path=r"^/jobs/(?:[^/]*-)?(\d{5,})"),
        PatternAdapter(
            JobSource.INDEED, ("indeed.com", "indeed.de"), query=("jk", "vjk"), keep_query=("jk",)
        ),
        PatternAdapter(
            JobSource.ARBEITSAGENTUR,
            ("arbeitsagentur.de",),
            path=r"/jobsuche/jobdetail/([A-Za-z0-9-]+)",
        ),
        PatternAdapter(
            JobSource.GLASSDOOR,
            ("glassdoor.de", "glassdoor.com", "glassdoor.co.uk", "glassdoor.at", "glassdoor.ch"),
            query=("jl", "jobListingId"),
            keep_query=("jl",),
        ),
        PatternAdapter(
            JobSource.PERSONIO,
            ("jobs.personio.de", "jobs.personio.com"),
            path=r"^/job/(\d+)",
            tenant_from_host=True,
        ),
        GreenhouseAdapter(),
        PatternAdapter(JobSource.LEVER, ("lever.co",), path=r"^/([^/]+)/([0-9a-fA-F-]{36})"),
        PatternAdapter(
            JobSource.SOFTGARDEN,
            ("softgarden.io", "softgarden.de"),
            path=r"^/job/(\d+)",
            tenant_from_host=True,
        ),
        PatternAdapter(JobSource.JOIN, ("join.com",), path=r"^/companies/([^/]+)/(\d+)"),
        PatternAdapter(
            JobSource.WORKDAY,
            ("myworkdayjobs.com",),
            path=r"/job/(?:.*/)?[^/]*_([A-Za-z0-9-]+)/?$",
            tenant_from_host=True,
        ),
    ]


class GenericAdapter(SourceAdapter):
    """Fallback für Karriereseiten und andere Jobbörsen."""

    source = JobSource.OTHER

    def matches(self, parts: SplitResult) -> bool:
        return True

    def identify(self, parts: SplitResult) -> SourceReference:
        return SourceReference(source=self.source, url_normalized=strip_tracking(parts))
