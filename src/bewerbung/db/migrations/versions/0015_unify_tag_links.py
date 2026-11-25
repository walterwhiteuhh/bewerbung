"""unify posting_tags into tag_links

Stellen-Hashtags wandern nach ``tag_links`` (``entity_type = 'posting'``): ein Mechanismus
für alle Objekttypen. ``posting_tags`` entfällt, Zeiträume und Herkunft bleiben erhalten.

Revision ID: 0015
Revises: 0014
Create Date: 2026-11-25 22:10:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import bewerbung.db.types

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_VIEWS = ("v_tag_assignments", "v_orphan_tag_links")
_TRIGGER_TARGETS = (
    ("trg_job_postings_end_tag_links", "job_postings", "posting"),
    ("trg_companies_end_tag_links", "companies", "company"),
    ("trg_documents_end_tag_links", "documents", "document"),
    ("trg_search_profiles_end_tag_links", "search_profiles", "search_profile"),
)
_OLD_TYPES = "'company', 'document', 'search_profile'"
_NEW_TYPES = "'posting', 'company', 'document', 'search_profile'"


def _drop_dependents() -> None:
    """Sichten und Trigger vor dem Tabellenumbau entfernen (SQLite-Batch kopiert die Tabelle)."""
    for view in _VIEWS:
        op.execute(f"DROP VIEW IF EXISTS {view}")
    if op.get_bind().dialect.name == "sqlite":
        for name, _, _ in _TRIGGER_TARGETS:
            op.execute(f"DROP TRIGGER IF EXISTS {name}")


def _create_dependents(*, with_postings: bool) -> None:
    tables = {
        "company": "companies",
        "document": "documents",
        "search_profile": "search_profiles",
    }
    if with_postings:
        tables["posting"] = "job_postings"
    exists = " OR ".join(
        f"(tl.entity_type = '{etype}' AND NOT EXISTS "
        f"(SELECT 1 FROM {table} x WHERE x.id = tl.entity_id))"
        for etype, table in tables.items()
    )
    op.execute(
        f"""
        CREATE VIEW v_orphan_tag_links AS
        SELECT tl.id, tl.entity_type, tl.entity_id FROM tag_links tl
        WHERE tl.removed_at IS NULL AND ({exists})
        """
    )
    if with_postings:
        op.execute(
            """
            CREATE VIEW v_tag_assignments AS
            SELECT tl.entity_type, tl.entity_id, tl.tag_id, t.key AS tag_key,
                   tl.origin, tl.added_at, tl.removed_at
            FROM tag_links tl JOIN tags t ON t.id = tl.tag_id
            """
        )
    else:
        op.execute(
            """
            CREATE VIEW v_tag_assignments AS
            SELECT 'posting' AS entity_type, pt.posting_id AS entity_id, pt.tag_id,
                   t.key AS tag_key, pt.origin, pt.added_at, pt.removed_at
            FROM posting_tags pt JOIN tags t ON t.id = pt.tag_id
            UNION ALL
            SELECT tl.entity_type, tl.entity_id, tl.tag_id, t.key, tl.origin, tl.added_at,
                   tl.removed_at
            FROM tag_links tl JOIN tags t ON t.id = tl.tag_id
            """
        )
    if op.get_bind().dialect.name == "sqlite":
        for name, table, etype in _TRIGGER_TARGETS:
            if etype == "posting" and not with_postings:
                continue
            op.execute(
                f"""
                CREATE TRIGGER {name} AFTER DELETE ON {table}
                BEGIN
                  UPDATE tag_links SET removed_at = strftime('%Y-%m-%d %H:%M:%f', 'now')
                  WHERE entity_type = '{etype}' AND entity_id = OLD.id AND removed_at IS NULL;
                END
                """
            )


def upgrade() -> None:
    _drop_dependents()
    # Erst den Wertebereich erweitern, dann kopieren (sonst verletzt der CHECK die Zeilen).
    with op.batch_alter_table("tag_links", schema=None) as batch_op:
        batch_op.drop_constraint("entity_type", type_="check")
        batch_op.create_check_constraint("entity_type", f"entity_type IN ({_NEW_TYPES})")
    op.execute(
        """
        INSERT INTO tag_links (entity_type, entity_id, tag_id, origin, added_at, removed_at)
        SELECT 'posting', posting_id, tag_id, origin, added_at, removed_at
        FROM posting_tags ORDER BY id
        """
    )
    op.drop_table("posting_tags")
    _create_dependents(with_postings=True)


def downgrade() -> None:
    _drop_dependents()
    utc = bewerbung.db.types.UTCDateTime(timezone=True)
    op.create_table(
        "posting_tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("posting_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("added_at", utc, nullable=False),
        sa.Column("removed_at", utc, nullable=True),
        sa.ForeignKeyConstraint(
            ["posting_id"],
            ["job_postings.id"],
            name=op.f("fk_posting_tags_posting_id_job_postings"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["tags.id"], name=op.f("fk_posting_tags_tag_id_tags"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_posting_tags")),
    )
    with op.batch_alter_table("posting_tags", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_posting_tags_posting_id"), ["posting_id"], unique=False
        )
        batch_op.create_index("ix_posting_tags_tag_removed", ["tag_id", "removed_at"])
        batch_op.create_index(
            "uq_posting_tags_active",
            ["posting_id", "tag_id"],
            unique=True,
            sqlite_where=sa.text("removed_at IS NULL"),
            postgresql_where=sa.text("removed_at IS NULL"),
        )
    op.execute(
        """
        INSERT INTO posting_tags (posting_id, tag_id, origin, added_at, removed_at)
        SELECT entity_id, tag_id, origin, added_at, removed_at
        FROM tag_links WHERE entity_type = 'posting' ORDER BY id
        """
    )
    op.execute("DELETE FROM tag_links WHERE entity_type = 'posting'")
    with op.batch_alter_table("tag_links", schema=None) as batch_op:
        batch_op.drop_constraint("entity_type", type_="check")
        batch_op.create_check_constraint("entity_type", f"entity_type IN ({_OLD_TYPES})")
    _create_dependents(with_postings=False)
