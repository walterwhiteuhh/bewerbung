"""unify validity period columns to started_at / ended_at

Zuordnungen mit Gültigkeitszeitraum heißen jetzt einheitlich ``started_at`` .. ``ended_at``
(offen = ``ended_at IS NULL``):

* ``tag_links``: added_at/removed_at
* ``tag_relations``: created_at/removed_at
* ``posting_documents``: attached_at/detached_at

``ALTER TABLE ... RENAME COLUMN`` passt partielle Indizes automatisch an; Sichten und Trigger
werden neu angelegt.

Revision ID: 0016
Revises: 0015
Create Date: 2026-11-25 22:50:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# (Tabelle, alter Name, neuer Name)
_RENAMES = (
    ("tag_links", "added_at", "started_at"),
    ("tag_links", "removed_at", "ended_at"),
    ("tag_relations", "created_at", "started_at"),
    ("tag_relations", "removed_at", "ended_at"),
    ("posting_documents", "attached_at", "started_at"),
    ("posting_documents", "detached_at", "ended_at"),
)
_VIEWS = ("v_tag_assignments", "v_orphan_tag_links")
_TRIGGERS = (
    ("trg_job_postings_end_tag_links", "job_postings", "posting"),
    ("trg_companies_end_tag_links", "companies", "company"),
    ("trg_documents_end_tag_links", "documents", "document"),
    ("trg_search_profiles_end_tag_links", "search_profiles", "search_profile"),
)


def _drop_dependents() -> None:
    for view in _VIEWS:
        op.execute(f"DROP VIEW IF EXISTS {view}")
    if op.get_bind().dialect.name == "sqlite":
        for name, _, _ in _TRIGGERS:
            op.execute(f"DROP TRIGGER IF EXISTS {name}")


def _create_dependents(start: str, end: str) -> None:
    tables = {
        "posting": "job_postings",
        "company": "companies",
        "document": "documents",
        "search_profile": "search_profiles",
    }
    exists = " OR ".join(
        f"(tl.entity_type = '{etype}' AND NOT EXISTS "
        f"(SELECT 1 FROM {table} x WHERE x.id = tl.entity_id))"
        for etype, table in tables.items()
    )
    op.execute(
        f"""
        CREATE VIEW v_orphan_tag_links AS
        SELECT tl.id, tl.entity_type, tl.entity_id FROM tag_links tl
        WHERE tl.{end} IS NULL AND ({exists})
        """
    )
    op.execute(
        f"""
        CREATE VIEW v_tag_assignments AS
        SELECT tl.entity_type, tl.entity_id, tl.tag_id, t.key AS tag_key, tl.origin,
               tl.{start} AS {start}, tl.{end} AS {end}
        FROM tag_links tl JOIN tags t ON t.id = tl.tag_id
        """
    )
    if op.get_bind().dialect.name == "sqlite":
        for name, table, etype in _TRIGGERS:
            op.execute(
                f"""
                CREATE TRIGGER {name} AFTER DELETE ON {table}
                BEGIN
                  UPDATE tag_links SET {end} = strftime('%Y-%m-%d %H:%M:%f', 'now')
                  WHERE entity_type = '{etype}' AND entity_id = OLD.id AND {end} IS NULL;
                END
                """
            )


def _rename(pairs: Sequence[tuple[str, str, str]], *, reverse: bool) -> None:
    for table, old, new in pairs:
        a, b = (new, old) if reverse else (old, new)
        op.execute(f"ALTER TABLE {table} RENAME COLUMN {a} TO {b}")


def upgrade() -> None:
    _drop_dependents()
    op.drop_index("ix_tag_links_tag_removed", table_name="tag_links")
    _rename(_RENAMES, reverse=False)
    op.create_index("ix_tag_links_tag_ended", "tag_links", ["tag_id", "ended_at"])
    _create_dependents("started_at", "ended_at")


def downgrade() -> None:
    _drop_dependents()
    op.drop_index("ix_tag_links_tag_ended", table_name="tag_links")
    _rename(_RENAMES, reverse=True)
    op.create_index("ix_tag_links_tag_removed", "tag_links", ["tag_id", "removed_at"])
    _create_dependents("added_at", "removed_at")
