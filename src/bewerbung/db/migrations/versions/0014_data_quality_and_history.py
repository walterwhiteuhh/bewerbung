"""data quality, history and analytics views

* Labels: ``reason_code``/``offered_salary`` an Statusevents (Absagegrund, Gehalt)
* Historie: Profilversionen, Zeiträume des Haupt-Lebenslaufs
* ``job_postings``: ``title_key`` und Geodaten wie bei ``listings``
* ``tag_links``: CHECK auf ``entity_type`` und (SQLite) Trigger gegen verwaiste Zuordnungen
* Views für Auswertungen: Tag-Zuordnungen, Statusdauern, Projektions-Konsistenz

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-25 21:30:00.000000
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from hashlib import sha256

import sqlalchemy as sa
from alembic import op

import bewerbung.db.types
from bewerbung.domain.matching import title_key

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VIEWS = (
    "v_tag_assignments",
    "v_orphan_tag_links",
    "v_status_durations",
    "v_application_status_check",
)
_TRIGGERS = (
    ("trg_companies_end_tag_links", "companies", "company"),
    ("trg_documents_end_tag_links", "documents", "document"),
    ("trg_search_profiles_end_tag_links", "search_profiles", "search_profile"),
)
_PROFILE_FIELDS = (
    "full_name",
    "email",
    "phone",
    "address",
    "headline",
    "summary",
    "skills",
    "cv_text",
    "home_location",
    "home_lat",
    "home_lon",
    "max_distance_km",
    "signature",
)


def _seconds_between(start: str, end: str) -> str:
    """Differenz in Sekunden, dialektabhängig (SQLite speichert Zeiten als Text)."""
    if op.get_bind().dialect.name == "sqlite":
        return f"(julianday({end}) - julianday({start})) * 86400.0"
    return f"EXTRACT(EPOCH FROM ({end} - {start}))"


def upgrade() -> None:
    bind = op.get_bind()
    utc = bewerbung.db.types.UTCDateTime(timezone=True)

    # --- Labels am Statusevent ----------------------------------------------------------
    with op.batch_alter_table("application_status_events", schema=None) as batch_op:
        batch_op.add_column(sa.Column("reason_code", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("offered_salary", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("offered_currency", sa.String(length=3), nullable=True))
        batch_op.create_check_constraint(
            "offered_salary", "offered_salary IS NULL OR offered_salary >= 0"
        )

    # --- Profil-Verlauf -----------------------------------------------------------------
    op.create_table(
        "applicant_profile_versions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("profile_id", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", utc, nullable=False),
        sa.ForeignKeyConstraint(
            ["profile_id"],
            ["applicant_profiles.id"],
            name=op.f("fk_applicant_profile_versions_profile_id_applicant_profiles"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_applicant_profile_versions")),
    )
    with op.batch_alter_table("applicant_profile_versions", schema=None) as batch_op:
        batch_op.create_index(
            "ix_profile_versions_profile_created", ["profile_id", "created_at"], unique=False
        )
    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.add_column(sa.Column("profile_version_id", sa.Integer(), nullable=True))
        batch_op.create_index(
            batch_op.f("ix_applications_profile_version_id"), ["profile_version_id"], unique=False
        )
        batch_op.create_foreign_key(
            batch_op.f("fk_applications_profile_version_id_applicant_profile_versions"),
            "applicant_profile_versions",
            ["profile_version_id"],
            ["id"],
            ondelete="SET NULL",
        )

    # --- Zeiträume des Haupt-Lebenslaufs ------------------------------------------------
    op.create_table(
        "document_primary_periods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("started_at", utc, nullable=False),
        sa.Column("ended_at", utc, nullable=True),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_document_primary_periods_document_id_documents"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_document_primary_periods")),
    )
    with op.batch_alter_table("document_primary_periods", schema=None) as batch_op:
        batch_op.create_index("ix_document_primary_started", ["started_at"], unique=False)
        batch_op.create_index(
            "uq_document_primary_open",
            ["document_id"],
            unique=True,
            sqlite_where=sa.text("ended_at IS NULL"),
            postgresql_where=sa.text("ended_at IS NULL"),
        )

    # --- Stellen: abgeleitete Schlüssel und Geodaten ------------------------------------
    with op.batch_alter_table("job_postings", schema=None) as batch_op:
        batch_op.add_column(sa.Column("title_key", sa.String(length=255), nullable=True))
        batch_op.add_column(sa.Column("city", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("postal_code", sa.String(length=10), nullable=True))
        batch_op.add_column(sa.Column("region", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("lat", sa.Float(), nullable=True))
        batch_op.add_column(sa.Column("lon", sa.Float(), nullable=True))
        batch_op.create_index("ix_job_postings_company_title", ["company_id", "title_key"])

    # --- Tag-Zuordnungen: Wertebereich ---------------------------------------------------
    with op.batch_alter_table("tag_links", schema=None) as batch_op:
        batch_op.create_check_constraint(
            "entity_type", "entity_type IN ('company', 'document', 'search_profile')"
        )

    _backfill(bind)
    _create_views()
    if bind.dialect.name == "sqlite":
        _create_triggers()


def _backfill(bind: sa.engine.Connection) -> None:
    # title_key + Ort der verknüpften Anzeige (die älteste, sie entstand beim Anlegen).
    for pid, title in bind.execute(sa.text("SELECT id, title FROM job_postings")).all():
        bind.execute(
            sa.text("UPDATE job_postings SET title_key = :k WHERE id = :id"),
            {"k": title_key(title), "id": pid},
        )
    bind.execute(
        sa.text(
            """
            UPDATE job_postings SET
              city = (SELECT l.city FROM listings l WHERE l.posting_id = job_postings.id
                      ORDER BY l.id LIMIT 1),
              postal_code = (SELECT l.postal_code FROM listings l
                             WHERE l.posting_id = job_postings.id ORDER BY l.id LIMIT 1),
              region = (SELECT l.region FROM listings l WHERE l.posting_id = job_postings.id
                        ORDER BY l.id LIMIT 1),
              lat = (SELECT l.lat FROM listings l WHERE l.posting_id = job_postings.id
                     ORDER BY l.id LIMIT 1),
              lon = (SELECT l.lon FROM listings l WHERE l.posting_id = job_postings.id
                     ORDER BY l.id LIMIT 1)
            """
        )
    )

    now = datetime.now(UTC)
    # Startversion des Profils, damit schon der aktuelle Stand historisiert ist.
    cols = ", ".join(("id", *_PROFILE_FIELDS))
    for row in bind.execute(sa.text(f"SELECT {cols} FROM applicant_profiles")).mappings():
        snapshot = {f: row[f] for f in _PROFILE_FIELDS}
        if isinstance(snapshot["skills"], str):
            snapshot["skills"] = json.loads(snapshot["skills"])
        digest = sha256(
            json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
        bind.execute(
            sa.text(
                "INSERT INTO applicant_profile_versions (profile_id, content_hash, snapshot, created_at)"
                " VALUES (:p, :h, :s, :t)"
            ),
            {"p": row["id"], "h": digest, "s": json.dumps(snapshot, ensure_ascii=False), "t": now},
        )
    # Bestehende Haupt-Lebensläufe als offener Zeitraum ab letzter Änderung.
    bind.execute(
        sa.text(
            "INSERT INTO document_primary_periods (document_id, started_at) "
            "SELECT id, updated_at FROM documents WHERE is_primary = 1 AND archived_at IS NULL"
        )
        if bind.dialect.name == "sqlite"
        else sa.text(
            "INSERT INTO document_primary_periods (document_id, started_at) "
            "SELECT id, updated_at FROM documents WHERE is_primary AND archived_at IS NULL"
        )
    )


def _create_views() -> None:
    # Eine Sicht auf alle aktiven Hashtag-Zuordnungen, egal ob an Stelle oder anderem Objekt.
    op.execute(
        """
        CREATE VIEW v_tag_assignments AS
        SELECT 'posting' AS entity_type, pt.posting_id AS entity_id, pt.tag_id, t.key AS tag_key,
               pt.origin, pt.added_at, pt.removed_at
        FROM posting_tags pt JOIN tags t ON t.id = pt.tag_id
        UNION ALL
        SELECT tl.entity_type, tl.entity_id, tl.tag_id, t.key, tl.origin, tl.added_at, tl.removed_at
        FROM tag_links tl JOIN tags t ON t.id = tl.tag_id
        """
    )
    # Zuordnungen, deren Objekt nicht (mehr) existiert; muss leer sein.
    op.execute(
        """
        CREATE VIEW v_orphan_tag_links AS
        SELECT tl.id, tl.entity_type, tl.entity_id
        FROM tag_links tl
        WHERE tl.removed_at IS NULL AND (
          (tl.entity_type = 'company' AND NOT EXISTS
             (SELECT 1 FROM companies c WHERE c.id = tl.entity_id))
          OR (tl.entity_type = 'document' AND NOT EXISTS
             (SELECT 1 FROM documents d WHERE d.id = tl.entity_id))
          OR (tl.entity_type = 'search_profile' AND NOT EXISTS
             (SELECT 1 FROM search_profiles s WHERE s.id = tl.entity_id))
        )
        """
    )
    # Verweildauer je Statusabschnitt; der letzte Abschnitt ist offen (until_at/seconds NULL).
    secs = _seconds_between("e.occurred_at", "e.until_at")
    op.execute(
        f"""
        CREATE VIEW v_status_durations AS
        SELECT e.application_id, e.to_status AS status, e.reason_code,
               e.occurred_at AS entered_at, e.until_at,
               CASE WHEN e.until_at IS NULL THEN NULL ELSE {secs} END AS seconds_in_status
        FROM (
          SELECT application_id, to_status, reason_code, occurred_at,
                 LEAD(occurred_at) OVER (
                   PARTITION BY application_id ORDER BY occurred_at, id
                 ) AS until_at
          FROM application_status_events
        ) e
        """
    )
    # Wahrheit sind die Events; hier stehen nur Bewerbungen, deren Projektion abweicht.
    op.execute(
        """
        CREATE VIEW v_application_status_check AS
        SELECT a.id AS application_id, a.current_status AS projected_status,
               (SELECT e.to_status FROM application_status_events e
                WHERE e.application_id = a.id
                ORDER BY e.occurred_at DESC, e.id DESC LIMIT 1) AS event_status
        FROM applications a
        WHERE a.current_status IS NOT (
          SELECT e.to_status FROM application_status_events e
          WHERE e.application_id = a.id
          ORDER BY e.occurred_at DESC, e.id DESC LIMIT 1
        )
        """
        if op.get_bind().dialect.name == "sqlite"
        else """
        CREATE VIEW v_application_status_check AS
        SELECT a.id AS application_id, a.current_status AS projected_status,
               (SELECT e.to_status FROM application_status_events e
                WHERE e.application_id = a.id
                ORDER BY e.occurred_at DESC, e.id DESC LIMIT 1) AS event_status
        FROM applications a
        WHERE a.current_status IS DISTINCT FROM (
          SELECT e.to_status FROM application_status_events e
          WHERE e.application_id = a.id
          ORDER BY e.occurred_at DESC, e.id DESC LIMIT 1
        )
        """
    )


def _create_triggers() -> None:
    # Hartes Löschen eines Objekts beendet seine Tag-Zuordnungen (kein FK möglich,
    # weil entity_id auf mehrere Tabellen zeigt).
    for name, table, etype in _TRIGGERS:
        op.execute(
            f"""
            CREATE TRIGGER {name} AFTER DELETE ON {table}
            BEGIN
              UPDATE tag_links SET removed_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
              WHERE entity_type = '{etype}' AND entity_id = OLD.id AND removed_at IS NULL;
            END
            """
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        for name, _, _ in _TRIGGERS:
            op.execute(f"DROP TRIGGER IF EXISTS {name}")
    for view in _VIEWS:
        op.execute(f"DROP VIEW IF EXISTS {view}")

    with op.batch_alter_table("tag_links", schema=None) as batch_op:
        batch_op.drop_constraint("entity_type", type_="check")

    with op.batch_alter_table("job_postings", schema=None) as batch_op:
        batch_op.drop_index("ix_job_postings_company_title")
        for col in ("lon", "lat", "region", "postal_code", "city", "title_key"):
            batch_op.drop_column(col)

    op.drop_table("document_primary_periods")

    with op.batch_alter_table("applications", schema=None) as batch_op:
        batch_op.drop_constraint(
            "fk_applications_profile_version_id_applicant_profile_versions", type_="foreignkey"
        )
        batch_op.drop_index(batch_op.f("ix_applications_profile_version_id"))
        batch_op.drop_column("profile_version_id")
    op.drop_table("applicant_profile_versions")

    with op.batch_alter_table("application_status_events", schema=None) as batch_op:
        batch_op.drop_constraint("offered_salary", type_="check")
        batch_op.drop_column("offered_currency")
        batch_op.drop_column("offered_salary")
        batch_op.drop_column("reason_code")
