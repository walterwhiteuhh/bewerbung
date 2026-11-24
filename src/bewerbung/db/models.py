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
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Enum,
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
    applications: Mapped[list[Application]] = relationship(
        back_populates="posting", order_by="Application.id"
    )

    @property
    def application(self) -> Application | None:
        """Neueste Bewerbung; das Modell erlaubt mehrere (z. B. erneute Bewerbung)."""
        return self.applications[-1] if self.applications else None


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
