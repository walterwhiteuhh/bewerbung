"""Gemeinsame Typen der Such-Provider."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field

from bewerbung.domain.enums import JobSource, RemoteType


class SearchQuery(BaseModel):
    query: str = Field(min_length=1, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    radius_km: int | None = Field(default=None, ge=0, le=200)
    remote_only: bool = False
    limit: int = Field(default=50, ge=1, le=100)


class ListingDraft(BaseModel):
    """Einheitliches Format, in das jeder Provider seine Treffer übersetzt."""

    source: JobSource
    external_id: str
    url: str | None
    title: str
    company_name: str | None = None
    location: str | None = None
    remote_type: RemoteType = RemoteType.UNKNOWN
    employment_type: str | None = None
    salary_min: int | None = None
    salary_max: int | None = None
    salary_currency: str | None = None
    description: str | None = None
    posted_at: datetime | None = None
    raw: dict[str, Any] = Field(default_factory=dict)

    def content_hash(self) -> str:
        """Hash über die fachlichen Felder; ändert er sich, wurde die Anzeige überarbeitet."""
        fields = self.model_dump(
            include={
                "title",
                "company_name",
                "location",
                "remote_type",
                "employment_type",
                "salary_min",
                "salary_max",
                "description",
            },
            mode="json",
        )
        return hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()


class ProviderError(Exception):
    """Fehler eines einzelnen Providers; die Suche läuft mit den anderen weiter."""


class SearchProvider(Protocol):
    source: JobSource
    label: str

    @property
    def unavailable_reason(self) -> str | None:
        """None, wenn nutzbar, sonst ein Hinweis für die UI (z. B. fehlender API-Key)."""

    async def search(self, query: SearchQuery) -> list[ListingDraft]: ...
