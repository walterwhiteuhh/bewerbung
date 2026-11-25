"""tag links and relations

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-25 16:10:00.000000
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

import bewerbung.db.types
from bewerbung.domain.tag_graph import SEED_ALIASES, SEED_IMPLIES, SEED_RELATED

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tag_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_type", sa.String(length=24), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("added_at", bewerbung.db.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("removed_at", bewerbung.db.types.UTCDateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["tags.id"], name=op.f("fk_tag_links_tag_id_tags"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tag_links")),
    )
    with op.batch_alter_table("tag_links", schema=None) as batch_op:
        batch_op.create_index("ix_tag_links_entity", ["entity_type", "entity_id"], unique=False)
        batch_op.create_index("ix_tag_links_tag_removed", ["tag_id", "removed_at"], unique=False)
        batch_op.create_index(
            "uq_tag_links_active",
            ["entity_type", "entity_id", "tag_id"],
            unique=True,
            sqlite_where=sa.text("removed_at IS NULL"),
            postgresql_where=sa.text("removed_at IS NULL"),
        )

    op.create_table(
        "tag_relations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tag_key", sa.String(length=40), nullable=False),
        sa.Column("related_key", sa.String(length=40), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("origin", sa.String(length=16), nullable=False),
        sa.Column("created_at", bewerbung.db.types.UTCDateTime(timezone=True), nullable=False),
        sa.Column("removed_at", bewerbung.db.types.UTCDateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tag_relations")),
    )
    with op.batch_alter_table("tag_relations", schema=None) as batch_op:
        batch_op.create_index("ix_tag_relations_related", ["related_key", "kind"], unique=False)
        batch_op.create_index(
            "uq_tag_relations_active",
            ["tag_key", "related_key", "kind"],
            unique=True,
            sqlite_where=sa.text("removed_at IS NULL"),
            postgresql_where=sa.text("removed_at IS NULL"),
        )
    _seed()


def _seed() -> None:
    """Startverknüpfungen anlegen. Es entstehen keine Tags: Begriffe gelten über ihren Schlüssel."""
    rel = sa.table(
        "tag_relations",
        sa.column("tag_key", sa.String),
        sa.column("related_key", sa.String),
        sa.column("kind", sa.String),
        sa.column("origin", sa.String),
        sa.column("created_at", bewerbung.db.types.UTCDateTime(timezone=True)),
    )
    now = datetime.now(UTC)
    edges: list[tuple[str, str, str]] = []
    for child, parents in SEED_IMPLIES.items():
        edges += [(child, parent, "implies") for parent in parents]
    edges += [(a, b, "alias") for a, b in SEED_ALIASES]
    edges += [(a, b, "related") for a, b in SEED_RELATED]
    op.bulk_insert(
        rel,
        [
            {"tag_key": a, "related_key": b, "kind": k, "origin": "seed", "created_at": now}
            for a, b, k in edges
        ],
    )


def downgrade() -> None:
    with op.batch_alter_table("tag_relations", schema=None) as batch_op:
        batch_op.drop_index("uq_tag_relations_active")
        batch_op.drop_index("ix_tag_relations_related")
    op.drop_table("tag_relations")
    with op.batch_alter_table("tag_links", schema=None) as batch_op:
        batch_op.drop_index("uq_tag_links_active")
        batch_op.drop_index("ix_tag_links_tag_removed")
        batch_op.drop_index("ix_tag_links_entity")
    op.drop_table("tag_links")
