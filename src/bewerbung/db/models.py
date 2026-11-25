"""ORM-Modell.

Designprinzipien:
* Jede Tabelle hat eine stabile ID sowie ``created_at``/``updated_at`` (UTC).
* Statuswechsel werden append-only in ``application_status_events`` protokolliert.
  ``applications.current_status`` ist nur eine denormalisierte Projektion für
  schnelle Listen und Filter; die Wahrheit liegt in den Events.
* Events sind bitemporal: ``occurred_at`` (wann es fachlich passiert ist, darf
  rückdatiert werden) und ``recorded_at`` (wann es erfasst wurde). So lassen sich
  später Trainingsdaten "as of" einem Stichtag ohne Data Leakage rekonstruieren.
* Löschen ist ein Soft-Delete (``archived_at``), Rohdaten der Quelle bleiben in
  ``raw_payload`` erhalten.
* Hashtags hängen über ``posting_tags`` an Stellen. Entfernen setzt ``removed_at``
  statt zu löschen, sodass sich nachvollziehen lässt, wann eine Stelle wie
  eingeordnet war (Labels für spätere Modelle).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from bewerbung.db.types import UTCDateTime, utcnow
from bewerbung.domain.enums import ApplicationStatus, JobSource, RemoteType

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


def _enum(enum_cls: type[Any], name: str) -> Enum:
    # Werte (nicht Namen) speichern und als VARCHAR + CHECK abbilden: portabel und lesbar.
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        validate_strings=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
    )


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, onupdate=utcnow, nullable=False
    )


class Company(TimestampMixin, Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Normalisierter Schlüssel zum Zusammenführen ("SAP SE" vs. "sap se ").
    name_key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    website: Mapped[str | None] = mapped_column(String(2048))
    industry: Mapped[str | None] = mapped_column(String(120))
    location: Mapped[str | None] = mapped_column(String(255))
    # Externe URL (Portal/Karriereseite) oder eigener Pfad /api/logos/...
    logo_url: Mapped[str | None] = mapped_column(String(2048))
    # Herkunft des Logos: portal | website | manual; erlaubt späteres gezieltes Neuladen.
    logo_source: Mapped[str | None] = mapped_column(String(16))
    logo_fetched_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # {netz: profil_url}, z. B. {"linkedin": "https://www.linkedin.com/company/acme"}.
    social_links: Mapped[dict[str, str] | None] = mapped_column(JSON)

    postings: Mapped[list[JobPosting]] = relationship(back_populates="company")


class JobPosting(TimestampMixin, Base):
    __tablename__ = "job_postings"
    __table_args__ = (
        # Dublettenschutz pro Quelle, nur wenn die Quelle eine ID liefert.
        Index(
            "uq_job_postings_source_external_id",
            "source",
            "external_id",
            unique=True,
            sqlite_where=text("external_id IS NOT NULL"),
            postgresql_where=text("external_id IS NOT NULL"),
        ),
        Index("ix_job_postings_url_normalized", "url_normalized"),
        Index("ix_job_postings_source_created", "source", "created_at"),
        CheckConstraint(
            "salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max",
            name="salary_range",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    remote_type: Mapped[RemoteType] = mapped_column(
        _enum(RemoteType, "remote_type"), default=RemoteType.UNKNOWN, nullable=False
    )
    employment_type: Mapped[str | None] = mapped_column(String(64))
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    salary_currency: Mapped[str] = mapped_column(String(3), default="EUR", nullable=False)
    description: Mapped[str | None] = mapped_column(Text)

    source: Mapped[JobSource] = mapped_column(_enum(JobSource, "job_source"), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(128))
    url: Mapped[str | None] = mapped_column(String(2048))
    url_normalized: Mapped[str | None] = mapped_column(String(2048))
    # Unveränderte Rohdaten eines Importers (später LinkedIn/Stepstone-API).
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    posted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)

    company: Mapped[Company | None] = relationship(back_populates="postings", lazy="joined")
    listings: Mapped[list[Listing]] = relationship(back_populates="posting")
    applications: Mapped[list[Application]] = relationship(
        back_populates="posting", order_by="Application.id"
    )
    tag_links: Mapped[list[PostingTag]] = relationship(
        back_populates="posting", order_by="PostingTag.id"
    )

    @property
    def application(self) -> Application | None:
        """Neueste Bewerbung; das Modell erlaubt mehrere (z. B. erneute Bewerbung)."""
        return self.applications[-1] if self.applications else None

    @property
    def tags(self) -> list[str]:
        """Aktuell gesetzte Hashtags (ohne entfernte), alphabetisch."""
        return sorted(
            (link.tag.name for link in self.tag_links if link.removed_at is None),
            key=str.casefold,
        )


class Tag(TimestampMixin, Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Anzeigename in der zuerst verwendeten Schreibweise, z. B. "Python".
    name: Mapped[str] = mapped_column(String(40), nullable=False)
    # Normalisierter Schlüssel ("python"), über den Schreibvarianten zusammenfallen.
    key: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)


class PostingTag(Base):
    """Zuordnung Stelle <-> Hashtag mit Gültigkeitszeitraum (added_at .. removed_at)."""

    __tablename__ = "posting_tags"
    __table_args__ = (
        # Pro Stelle und Tag höchstens eine aktive Zuordnung.
        Index(
            "uq_posting_tags_active",
            "posting_id",
            "tag_id",
            unique=True,
            sqlite_where=text("removed_at IS NULL"),
            postgresql_where=text("removed_at IS NULL"),
        ),
        Index("ix_posting_tags_tag_removed", "tag_id", "removed_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    posting_id: Mapped[int] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), nullable=False)
    # Herkunft: "manual" (Formular/Detail), "note" (#tag in Notiz), "auto" (aus der Beschreibung).
    origin: Mapped[str] = mapped_column(String(16), default="manual", nullable=False)
    added_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    removed_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    posting: Mapped[JobPosting] = relationship(back_populates="tag_links")
    tag: Mapped[Tag] = relationship(lazy="joined")


class Application(TimestampMixin, Base):
    __tablename__ = "applications"
    __table_args__ = (
        Index("ix_applications_status_changed", "current_status", "status_changed_at"),
        CheckConstraint("priority BETWEEN 1 AND 5", name="priority_range"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    posting_id: Mapped[int] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    current_status: Mapped[ApplicationStatus] = mapped_column(
        _enum(ApplicationStatus, "application_status"), nullable=False
    )
    status_changed_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    priority: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(255))
    contact_email: Mapped[str | None] = mapped_column(String(255))
    follow_up_at: Mapped[datetime | None] = mapped_column(UTCDateTime, index=True)

    posting: Mapped[JobPosting] = relationship(back_populates="applications")
    events: Mapped[list[ApplicationStatusEvent]] = relationship(
        back_populates="application",
        order_by="(ApplicationStatusEvent.occurred_at, ApplicationStatusEvent.id)",
    )
    notes: Mapped[list[Note]] = relationship(
        back_populates="application", order_by="Note.created_at.desc()"
    )


class ApplicationStatusEvent(Base):
    """Append-only: wird nie geändert oder gelöscht."""

    __tablename__ = "application_status_events"
    __table_args__ = (
        Index("ix_status_events_app_occurred", "application_id", "occurred_at"),
        Index("ix_status_events_to_status", "to_status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False
    )
    from_status: Mapped[ApplicationStatus | None] = mapped_column(
        _enum(ApplicationStatus, "application_status")
    )
    to_status: Mapped[ApplicationStatus] = mapped_column(
        _enum(ApplicationStatus, "application_status"), nullable=False
    )
    note: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)

    application: Mapped[Application] = relationship(back_populates="events")


class Note(TimestampMixin, Base):
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    application_id: Mapped[int] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), nullable=False, index=True
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)

    application: Mapped[Application] = relationship(back_populates="notes")


class Listing(TimestampMixin, Base):
    """Eine Anzeige so, wie ein Portal sie zeigt (Rohsicht pro Quelle).

    * ``posting_id IS NULL``: Suchtreffer, noch nicht gemerkt.
    * Mehrere Listings können auf dieselbe Stelle zeigen (gleiche Stelle auf XING und Stepstone).
    * ``first_seen_at``/``last_seen_at`` stammen aus Suchläufen und ergeben die Laufzeit einer
      Anzeige; ``content_hash`` erkennt inhaltliche Änderungen zwischen zwei Läufen.
    """

    __tablename__ = "listings"
    __table_args__ = (
        Index(
            "uq_listings_source_external_id",
            "source",
            "external_id",
            unique=True,
            sqlite_where=text("external_id IS NOT NULL"),
            postgresql_where=text("external_id IS NOT NULL"),
        ),
        Index("ix_listings_url_normalized", "url_normalized"),
        Index("ix_listings_source_last_seen", "source", "last_seen_at"),
        Index("ix_listings_company_title", "company_id", "title_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    posting_id: Mapped[int | None] = mapped_column(
        ForeignKey("job_postings.id", ondelete="SET NULL"), index=True
    )
    source: Mapped[JobSource] = mapped_column(_enum(JobSource, "job_source"), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(128))
    url: Mapped[str | None] = mapped_column(String(2048))
    url_normalized: Mapped[str | None] = mapped_column(String(2048))

    title: Mapped[str] = mapped_column(String(500), nullable=False)
    company_name: Mapped[str | None] = mapped_column(String(255))
    company_logo_url: Mapped[str | None] = mapped_column(String(2048))
    # Abgeleitete Schlüssel für Querbezüge (gleiche Firma, gleiche Stelle auf anderen Portalen).
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id", ondelete="SET NULL"), index=True
    )
    title_key: Mapped[str | None] = mapped_column(String(255))
    # Strukturierter Ort aus den Rohdaten; Koordinaten nur, wenn die Quelle sie liefert.
    city: Mapped[str | None] = mapped_column(String(120))
    postal_code: Mapped[str | None] = mapped_column(String(10))
    region: Mapped[str | None] = mapped_column(String(120))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    location: Mapped[str | None] = mapped_column(String(255))
    remote_type: Mapped[RemoteType] = mapped_column(
        _enum(RemoteType, "remote_type"), default=RemoteType.UNKNOWN, nullable=False
    )
    employment_type: Mapped[str | None] = mapped_column(String(64))
    salary_min: Mapped[int | None] = mapped_column(Integer)
    salary_max: Mapped[int | None] = mapped_column(Integer)
    salary_currency: Mapped[str | None] = mapped_column(String(3))
    description: Mapped[str | None] = mapped_column(Text)
    posted_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    first_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    expired_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    content_hash: Mapped[str | None] = mapped_column(String(64))
    raw_payload: Mapped[dict[str, Any] | None] = mapped_column(JSON)

    posting: Mapped[JobPosting | None] = relationship(back_populates="listings")


class SearchProfile(TimestampMixin, Base):
    """Gespeicherte Suche, die man erneut ausführen kann."""

    __tablename__ = "search_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    query: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    radius_km: Mapped[int | None] = mapped_column(Integer)
    sources: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    remote_only: Mapped[bool] = mapped_column(default=False, nullable=False)
    work_times: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default=text("'[]'"), nullable=False
    )
    offer_type: Mapped[str] = mapped_column(
        String(32), default="arbeit", server_default="arbeit", nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    runs: Mapped[list[SearchRun]] = relationship(back_populates="profile")


class SearchRun(Base):
    """Ein Suchlauf (append-only). Parameter werden als Snapshot gespeichert,
    damit spätere Änderungen am Profil die Historie nicht verfälschen."""

    __tablename__ = "search_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    profile_id: Mapped[int | None] = mapped_column(
        ForeignKey("search_profiles.id", ondelete="SET NULL"), index=True
    )
    query: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    radius_km: Mapped[int | None] = mapped_column(Integer)
    sources: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    remote_only: Mapped[bool] = mapped_column(default=False, nullable=False)
    work_times: Mapped[list[str]] = mapped_column(
        JSON, default=list, server_default=text("'[]'"), nullable=False
    )
    offer_type: Mapped[str] = mapped_column(
        String(32), default="arbeit", server_default="arbeit", nullable=False
    )
    started_at: Mapped[datetime] = mapped_column(
        UTCDateTime, default=utcnow, nullable=False, index=True
    )
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    # Aus "Letzte Suchen" entfernt. Der Lauf bleibt für Auswertungen (gezeigt -> gemerkt) erhalten.
    hidden_at: Mapped[datetime | None] = mapped_column(UTCDateTime)
    total_hits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_hits: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    errors: Mapped[list[dict[str, str]]] = mapped_column(JSON, default=list, nullable=False)

    profile: Mapped[SearchProfile | None] = relationship(back_populates="runs")
    hits: Mapped[list[SearchHit]] = relationship(back_populates="run", order_by="SearchHit.rank")


class SearchHit(Base):
    """Treffer eines Laufs mit Rang. Zusammen mit ``listings.posting_id`` entsteht daraus
    später ein Trainingsdatensatz (gezeigt -> gemerkt) für ein Relevanz-Ranking."""

    __tablename__ = "search_hits"
    __table_args__ = (
        Index("uq_search_hits_run_listing", "run_id", "listing_id", unique=True),
        Index("ix_search_hits_listing", "listing_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    run_id: Mapped[int] = mapped_column(
        ForeignKey("search_runs.id", ondelete="CASCADE"), nullable=False
    )
    listing_id: Mapped[int] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), nullable=False
    )
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    is_new: Mapped[bool] = mapped_column(default=False, nullable=False)

    run: Mapped[SearchRun] = relationship(back_populates="hits")
    listing: Mapped[Listing] = relationship(lazy="joined")


class ApplicantProfile(TimestampMixin, Base):
    """Bewerberprofil als Grundlage für Anschreiben (aktuell genau eins)."""

    __tablename__ = "applicant_profiles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(64))
    address: Mapped[str | None] = mapped_column(String(500))
    headline: Mapped[str | None] = mapped_column(String(255))
    summary: Mapped[str | None] = mapped_column(Text)
    skills: Mapped[list[str]] = mapped_column(JSON, default=list, nullable=False)
    cv_text: Mapped[str | None] = mapped_column(Text)
    # Wohnort für Entfernungen; Koordinaten werden aus bekannten Orten abgeleitet.
    home_location: Mapped[str | None] = mapped_column(String(255))
    home_lat: Mapped[float | None] = mapped_column(Float)
    home_lon: Mapped[float | None] = mapped_column(Float)
    max_distance_km: Mapped[int | None] = mapped_column(Integer)

    @property
    def home_located(self) -> bool:
        return self.home_lat is not None and self.home_lon is not None

    signature: Mapped[str | None] = mapped_column(Text)


class CoverLetter(TimestampMixin, Base):
    """Eine Anschreiben-Version zu einer Stelle.

    ``body_generated`` bleibt unverändert, ``body`` ist die bearbeitete Fassung: die
    Differenz zeigt später, wie viel nachgebessert werden musste. ``input_snapshot``
    hält genau die Eingaben fest (Stelle, Hashtags, Profil, Optionen), mit denen der
    Text entstand, damit Ergebnisse reproduzierbar und auswertbar bleiben.
    """

    __tablename__ = "cover_letters"
    __table_args__ = (
        Index("uq_cover_letters_posting_version", "posting_id", "version", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    posting_id: Mapped[int] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False
    )
    application_id: Mapped[int | None] = mapped_column(
        ForeignKey("applications.id", ondelete="SET NULL"), index=True
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    # "draft" oder "final" (die verschickte Fassung).
    status: Mapped[str] = mapped_column(String(16), default="draft", nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    body_generated: Mapped[str] = mapped_column(Text, nullable=False)
    generator: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str | None] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(16), nullable=False)
    tone: Mapped[str] = mapped_column(String(32), nullable=False)
    input_snapshot: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    duration_ms: Mapped[int | None] = mapped_column(Integer)

    posting: Mapped[JobPosting] = relationship()


class Document(TimestampMixin, Base):
    """Hochgeladene Unterlage (Lebenslauf, Zeugnis, Zertifikat ...).

    Die Datei liegt inhaltsadressiert (``sha256``) im Dokumentenordner, nie unter dem
    Namen, den der Browser mitschickt. ``text_content`` ist der ausgelesene Text samt
    Extraktor-Version, damit er später neu berechnet oder für Features genutzt werden kann.
    """

    __tablename__ = "documents"
    __table_args__ = (
        Index(
            "uq_documents_sha256_active",
            "sha256",
            unique=True,
            sqlite_where=text("archived_at IS NULL"),
            postgresql_where=text("archived_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(128), nullable=False)
    page_count: Mapped[int | None] = mapped_column(Integer)
    text_content: Mapped[str | None] = mapped_column(Text)
    extractor_version: Mapped[str | None] = mapped_column(String(16))
    is_primary: Mapped[bool] = mapped_column(default=False, nullable=False)
    archived_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class PostingDocument(TimestampMixin, Base):
    """Welche Unterlagen zu einer Bewerbung gehören. Entfernen setzt ``detached_at``."""

    __tablename__ = "posting_documents"
    __table_args__ = (
        Index(
            "uq_posting_documents_active",
            "posting_id",
            "document_id",
            unique=True,
            sqlite_where=text("detached_at IS NULL"),
            postgresql_where=text("detached_at IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    posting_id: Mapped[int] = mapped_column(
        ForeignKey("job_postings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attached_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow, nullable=False)
    detached_at: Mapped[datetime | None] = mapped_column(UTCDateTime)

    document: Mapped[Document] = relationship()
