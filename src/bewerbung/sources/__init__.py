"""Quellen-Abstraktion: jede Jobbörse ist ein ``SourceAdapter``."""

from bewerbung.sources.base import JobPostingDraft, SourceAdapter, SourceReference
from bewerbung.sources.registry import SourceRegistry, default_registry

__all__ = [
    "JobPostingDraft",
    "SourceAdapter",
    "SourceReference",
    "SourceRegistry",
    "default_registry",
]
