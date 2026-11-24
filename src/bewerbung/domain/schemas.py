"""Pydantic-Schemas für API-Ein- und -Ausgabe."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal, Self

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)

from bewerbung.domain.enums import ApplicationStatus, JobSource, RemoteType


def _strip_or_none(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _to_utc(value: datetime) -> datetime:
    return value.astimezone(UTC)


# Eingehende Zeitstempel müssen eine Zeitzone haben und werden nach UTC normalisiert.
UtcDatetime = Annotated[AwareDatetime, AfterValidator(_to_utc)]
OptStr = Annotated[str | None, AfterValidator(_strip_or_none)]
Priority = Annotated[int, Field(ge=1, le=5)]


class _Schema(BaseModel):
    model_config = ConfigDict(from_attributes=True, str_strip_whitespace=True)


# --- Quellen -----------------------------------------------------------------


class SourceDetection(_Schema):
    source: JobSource
    external_id: str | None
    url_normalized: str
    duplicate_of: int | None = Field(
        default=None, description="ID einer bereits erfassten Stelle mit gleicher Quelle/URL"
    )


# --- Stellenanzeigen ---------------------------------------------------------


class _PostingFields(_Schema):
    location: OptStr = Field(default=None, max_length=255)
    remote_type: RemoteType = RemoteType.UNKNOWN
    employment_type: OptStr = Field(default=None, max_length=64)
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    salary_currency: str = Field(default="EUR", min_length=3, max_length=3)
    description: OptStr = None
    posted_at: UtcDatetime | None = None

    @model_validator(mode="after")
    def _check_salary(self) -> Self:
        if (
            self.salary_min is not None
            and self.salary_max is not None
            and self.salary_min > self.salary_max
        ):
            raise ValueError("salary_min darf nicht größer als salary_max sein")
        return self


class PostingCreate(_PostingFields):
    title: str = Field(min_length=1, max_length=500)
    company_name: OptStr = Field(default=None, max_length=255)
    url: OptStr = Field(default=None, max_length=2048)
    source: JobSource | None = Field(
        default=None, description="Leer lassen: wird aus der URL erkannt (sonst 'manual')"
    )
    external_id: OptStr = Field(default=None, max_length=128)
    raw_payload: dict[str, Any] | None = None

    initial_status: ApplicationStatus = ApplicationStatus.SAVED
    priority: Priority = 3


class PostingUpdate(_Schema):
    """Teil-Update: nur gesetzte Felder werden übernommen."""

    title: str | None = Field(default=None, min_length=1, max_length=500)
    company_name: OptStr = Field(default=None, max_length=255)
    location: OptStr = Field(default=None, max_length=255)
    remote_type: RemoteType | None = None
    employment_type: OptStr = Field(default=None, max_length=64)
    salary_min: int | None = Field(default=None, ge=0)
    salary_max: int | None = Field(default=None, ge=0)
    salary_currency: str | None = Field(default=None, min_length=3, max_length=3)
    description: OptStr = None
    url: OptStr = Field(default=None, max_length=2048)
    posted_at: UtcDatetime | None = None


class CompanyRead(_Schema):
    id: int
    name: str


class ApplicationSummary(_Schema):
    id: int
    current_status: ApplicationStatus
    status_changed_at: datetime
    applied_at: datetime | None
    priority: int
    follow_up_at: datetime | None


class PostingListItem(_Schema):
    id: int
    title: str
    company: CompanyRead | None
    location: str | None
    remote_type: RemoteType
    source: JobSource
    url: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str
    created_at: datetime
    updated_at: datetime
    application: ApplicationSummary | None


class PostingPage(_Schema):
    items: list[PostingListItem]
    total: int
    limit: int
    offset: int


# --- Bewerbungen -------------------------------------------------------------


class StatusEventRead(_Schema):
    id: int
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus
    note: str | None
    occurred_at: datetime
    recorded_at: datetime


class NoteRead(_Schema):
    id: int
    body: str
    created_at: datetime
    updated_at: datetime


class ApplicationRead(ApplicationSummary):
    posting_id: int
    contact_name: str | None
    contact_email: str | None
    created_at: datetime
    updated_at: datetime
    events: list[StatusEventRead]
    notes: list[NoteRead]


class PostingDetail(PostingListItem):
    employment_type: str | None
    description: str | None
    external_id: str | None
    url_normalized: str | None
    posted_at: datetime | None
    archived_at: datetime | None
    application: ApplicationRead | None


class StatusChange(_Schema):
    status: ApplicationStatus
    note: OptStr = None
    occurred_at: UtcDatetime | None = Field(
        default=None, description="Fachlicher Zeitpunkt; leer = jetzt. Rückdatieren erlaubt."
    )


class ApplicationUpdate(_Schema):
    priority: Priority | None = None
    contact_name: OptStr = Field(default=None, max_length=255)
    contact_email: OptStr = Field(default=None, max_length=255)
    follow_up_at: UtcDatetime | None = None


class NoteCreate(_Schema):
    body: str = Field(min_length=1, max_length=20_000)


# --- Filter & Statistik ------------------------------------------------------

SortField = Literal["created_at", "updated_at", "status_changed_at", "priority", "title"]


class PostingFilter(_Schema):
    q: OptStr = None
    status: list[ApplicationStatus] = Field(default_factory=list)
    source: list[JobSource] = Field(default_factory=list)
    include_archived: bool = False
    sort: SortField = "updated_at"
    order: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class CountBucket(_Schema):
    key: str
    count: int


class Stats(_Schema):
    total: int
    active: int
    by_status: list[CountBucket]
    by_source: list[CountBucket]
    response_rate: float | None = Field(
        description="Anteil beworbener Stellen mit Rückmeldung (über 'applied' hinaus)"
    )
