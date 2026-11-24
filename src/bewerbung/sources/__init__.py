"""Quellen-Abstraktion: jede Jobbörse ist ein ``SourceAdapter``."""

from bewerbung.sources.base import SourceAdapter, SourceReference
from bewerbung.sources.registry import SourceRegistry, default_registry

__all__ = [
    "SourceAdapter",
    "SourceReference",
    "SourceRegistry",
    "default_registry",
]
