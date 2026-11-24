"""Konkrete Adapter. Reine URL-Logik, damit sie schnell und ohne Netzwerk testbar sind."""

from __future__ import annotations

import re
from urllib.parse import SplitResult, parse_qs

from bewerbung.domain.enums import JobSource
from bewerbung.sources.base import SourceAdapter, SourceReference, strip_tracking


def _host(parts: SplitResult) -> str:
    return (parts.hostname or "").lower()


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
        return reference.url_normalized if reference.external_id else original_url


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


class GenericAdapter(SourceAdapter):
    """Fallback für Karriereseiten und andere Jobbörsen."""

    source = JobSource.OTHER

    def matches(self, parts: SplitResult) -> bool:
        return True

    def identify(self, parts: SplitResult) -> SourceReference:
        return SourceReference(source=self.source, url_normalized=strip_tracking(parts))
