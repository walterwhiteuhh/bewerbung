"""Registry: findet den passenden Adapter zu einer URL."""

from __future__ import annotations

from collections.abc import Sequence
from functools import lru_cache

from bewerbung.domain.enums import JobSource
from bewerbung.sources.adapters import GenericAdapter, LinkedInAdapter, StepstoneAdapter
from bewerbung.sources.base import SourceAdapter, SourceReference, parse_url


class SourceRegistry:
    def __init__(self, adapters: Sequence[SourceAdapter], fallback: SourceAdapter) -> None:
        self._adapters = list(adapters)
        self._fallback = fallback

    def register(self, adapter: SourceAdapter) -> None:
        self._adapters.insert(0, adapter)

    def adapter_for(self, url: str) -> SourceAdapter:
        parts = parse_url(url)
        return next((a for a in self._adapters if a.matches(parts)), self._fallback)

    def identify(self, url: str) -> SourceReference:
        return self.adapter_for(url).identify(parse_url(url))

    def get(self, source: JobSource) -> SourceAdapter | None:
        return next((a for a in self._adapters if a.source is source), None)


@lru_cache
def default_registry() -> SourceRegistry:
    return SourceRegistry([LinkedInAdapter(), StepstoneAdapter()], fallback=GenericAdapter())
