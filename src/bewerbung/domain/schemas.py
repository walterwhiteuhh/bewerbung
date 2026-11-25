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

from bewerbung.domain.enums import ApplicationStatus, JobSource, OfferType, RemoteType, WorkTime
from bewerbung.domain.tags import unique_tags


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
# Hashtags: bereinigt ("#Python " -> "Python"), Dubletten unabhängig von Groß-/Kleinschreibung weg.
TagList = Annotated[list[str], Field(max_length=30), AfterValidator(unique_tags)]


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


class ImportRequest(_Schema):
    url: str = Field(min_length=4, max_length=2048)


class ImportPreview(_Schema):
    """Vorschlag aus der geladenen Seite; wird nicht gespeichert, das Formular übernimmt ihn."""

    detection: SourceDetection
    method: str = Field(description="'json-ld', 'opengraph' oder 'none'")
    title: str | None
    company_name: str | None
    company_logo_url: str | None = None
    location: str | None
    remote_type: RemoteType
    employment_type: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    description: str | None
    posted_at: datetime | None
    raw_payload: dict[str, Any] = Field(
        description="Rohdaten plus Metadaten (fetched_at, extractor); beim Anlegen mitsenden"
    )
    suggested_tags: list[str] = Field(
        default_factory=list, description="Aus Titel/Beschreibung erkannte Hashtags"
    )
    warnings: list[str] = Field(default_factory=list)


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
    company_logo_url: OptStr = Field(
        default=None, max_length=2048, description="Leer: wird aus raw_payload gelesen"
    )
    url: OptStr = Field(default=None, max_length=2048)
    source: JobSource | None = Field(
        default=None, description="Leer lassen: wird aus der URL erkannt (sonst 'manual')"
    )
    external_id: OptStr = Field(default=None, max_length=128)
    raw_payload: dict[str, Any] | None = None

    initial_status: ApplicationStatus = ApplicationStatus.SAVED
    priority: Priority = 3
    tags: TagList = Field(default_factory=list)


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
    tags: TagList | None = Field(default=None, description="Ersetzt alle Hashtags der Stelle")


class CompanyRead(_Schema):
    id: int
    name: str
    logo_url: str | None = None


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
    tags: list[str] = Field(default_factory=list)


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
    remote: list[RemoteType] = Field(default_factory=list)
    tag: TagList = Field(
        default_factory=list, description="Nur Stellen mit allen genannten Hashtags"
    )
    location: OptStr = None
    min_salary: int | None = Field(default=None, ge=0)
    follow_up_due: bool = False
    include_archived: bool = False
    sort: SortField = "updated_at"
    order: Literal["asc", "desc"] = "desc"
    limit: int = Field(default=50, ge=1, le=200)
    offset: int = Field(default=0, ge=0)


class TagCount(_Schema):
    name: str
    count: int


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


# --- Live-Suche ----------------------------------------------------------------


class ProviderInfo(_Schema):
    source: JobSource
    label: str
    available: bool
    reason: str | None = None


class SearchRequest(_Schema):
    query: str = Field(min_length=1, max_length=255)
    location: OptStr = Field(default=None, max_length=255)
    radius_km: int | None = Field(default=None, ge=0, le=200)
    remote_only: bool = False
    work_times: list[WorkTime] = Field(default_factory=list, description="Leer = alle")
    offer_type: OfferType = "arbeit"
    sources: list[JobSource] = Field(
        default_factory=list, description="Leer = alle verfügbaren Provider"
    )
    profile_id: int | None = None


class ListingRead(_Schema):
    id: int
    posting_id: int | None
    source: JobSource
    external_id: str | None
    url: str | None
    title: str
    company_name: str | None
    company_logo_url: str | None = None
    location: str | None
    remote_type: RemoteType
    employment_type: str | None
    salary_min: int | None
    salary_max: int | None
    salary_currency: str | None
    description: str | None
    posted_at: datetime | None
    first_seen_at: datetime
    last_seen_at: datetime


class SearchHitRead(_Schema):
    rank: int
    is_new: bool
    listing: ListingRead


class SearchError(_Schema):
    source: str
    message: str


class SearchRunSummary(_Schema):
    id: int
    profile_id: int | None
    query: str
    location: str | None
    radius_km: int | None
    remote_only: bool
    work_times: list[str]
    offer_type: str
    sources: list[str]
    started_at: datetime
    finished_at: datetime | None
    total_hits: int
    new_hits: int
    errors: list[SearchError]


class SearchRunRead(SearchRunSummary):
    hits: list[SearchHitRead]


class SearchProfileCreate(_Schema):
    name: str = Field(min_length=1, max_length=120)
    query: str = Field(min_length=1, max_length=255)
    location: OptStr = Field(default=None, max_length=255)
    radius_km: int | None = Field(default=None, ge=0, le=200)
    remote_only: bool = False
    work_times: list[WorkTime] = Field(default_factory=list)
    offer_type: OfferType = "arbeit"
    sources: list[JobSource] = Field(default_factory=list)


class SearchProfileRead(SearchProfileCreate):
    id: int
    created_at: datetime


class SaveListing(_Schema):
    initial_status: ApplicationStatus = ApplicationStatus.SAVED
    priority: Priority = 3
    tags: TagList = Field(default_factory=list)


# --- Profil & Anschreiben ----------------------------------------------------


class ProfileRead(_Schema):
    full_name: str | None
    email: str | None
    phone: str | None
    address: str | None
    headline: str | None
    summary: str | None
    skills: list[str]
    cv_text: str | None
    signature: str | None
    updated_at: datetime | None = None


class ProfileUpdate(_Schema):
    full_name: OptStr = Field(default=None, max_length=255)
    email: OptStr = Field(default=None, max_length=255)
    phone: OptStr = Field(default=None, max_length=64)
    address: OptStr = Field(default=None, max_length=500)
    headline: OptStr = Field(default=None, max_length=255)
    summary: OptStr = Field(default=None, max_length=10_000)
    skills: list[Annotated[str, Field(min_length=1, max_length=60)]] = Field(
        default_factory=list, max_length=60
    )
    cv_text: OptStr = Field(default=None, max_length=50_000)
    signature: OptStr = Field(default=None, max_length=1_000)


GeneratorName = Literal["claude", "openai", "gemini", "template"]


class GeneratorInfo(_Schema):
    name: GeneratorName
    label: str
    available: bool
    reason: str | None = None
    model: str | None = None


class CoverLetterRequest(_Schema):
    generator: Literal["auto"] | GeneratorName = "auto"
    tone: Literal["formell", "modern", "locker"] = "modern"
    length: Literal["kurz", "normal", "ausfuehrlich"] = "normal"
    extra_notes: OptStr = Field(default=None, max_length=4_000)


class CoverLetterUpdate(_Schema):
    body: str | None = Field(default=None, min_length=1, max_length=20_000)
    status: Literal["draft", "final"] | None = None


class CoverLetterRead(_Schema):
    id: int
    posting_id: int
    version: int
    status: str
    body: str
    edited: bool
    generator: str
    model: str | None
    tone: str
    input_snapshot: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class LetterContextPreview(_Schema):
    """Was automatisch erkannt wurde, bevor ein Anschreiben erzeugt wird."""

    portal: str | None
    tags: list[str]
    suggested_tags: list[str]
    description_excerpt: str | None
    matching_skills: list[str]
    profile_complete: bool
    missing_profile_fields: list[str]


# --- Unterlagen ----------------------------------------------------------------

DocumentKind = Literal["lebenslauf", "zeugnis", "zertifikat", "anschreiben", "sonstiges"]


class DocumentRead(_Schema):
    id: int
    kind: DocumentKind
    title: str
    filename: str
    content_type: str
    size_bytes: int
    page_count: int | None
    has_text: bool
    text_preview: str | None
    is_primary: bool
    created_at: datetime
    archived_at: datetime | None


class DocumentUpdate(_Schema):
    kind: DocumentKind | None = None
    title: str | None = Field(default=None, min_length=1, max_length=255)
    is_primary: bool | None = None


class DocumentText(_Schema):
    id: int
    text: str | None


class PostingDocumentsUpdate(_Schema):
    document_ids: list[int] = Field(default_factory=list, max_length=50)
