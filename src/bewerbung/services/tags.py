"""Hashtags setzen und ergänzen: ein Mechanismus für alle Objekttypen (``tag_links``)."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from bewerbung.db.models import JobPosting, Tag, TagLink
from bewerbung.db.types import utcnow
from bewerbung.domain.enums import TagEntity
from bewerbung.domain.tags import unique_tags

logger = logging.getLogger(__name__)


def get_or_create_tags(session: Session, names: list[str]) -> list[Tag]:
    wanted = {name.casefold(): name for name in unique_tags(names)}
    if not wanted:
        return []
    existing = {t.key: t for t in session.scalars(select(Tag).where(Tag.key.in_(wanted)))}
    for key, name in wanted.items():
        if key not in existing:
            tag = Tag(name=name, key=key)
            session.add(tag)
            existing[key] = tag
    session.flush()
    return [existing[key] for key in wanted]


def active_links(session: Session, entity_type: str, entity_id: int) -> dict[int, TagLink]:
    """Aktive Zuordnungen eines Objekts, nach ``tag_id``."""
    return {
        link.tag_id: link
        for link in session.scalars(
            select(TagLink).where(
                TagLink.entity_type == entity_type,
                TagLink.entity_id == entity_id,
                TagLink.ended_at.is_(None),
            )
        )
    }


def link_tags(
    session: Session,
    entity_type: str,
    entity_id: int,
    names: list[str],
    *,
    origin: str = "manual",
    replace: bool = False,
) -> list[Tag]:
    """Ordnet Hashtags einem Objekt zu.

    ``replace=False`` ergänzt (bereits gesetzte bleiben unverändert); ``replace=True`` setzt
    genau diese Menge, nicht mehr gewünschte Zuordnungen werden mit ``ended_at`` beendet
    statt gelöscht (Historie).
    """
    tags = get_or_create_tags(session, names)
    active = active_links(session, entity_type, entity_id)
    if replace:
        wanted = {t.id for t in tags}
        now = utcnow()
        for tag_id, link in active.items():
            if tag_id not in wanted:
                link.ended_at = now
    for tag in tags:
        if tag.id not in active:
            session.add(
                TagLink(entity_type=entity_type, entity_id=entity_id, tag_id=tag.id, origin=origin)
            )
    session.flush()
    return tags


def drop_entity_tags(session: Session, entity_type: str, entity_id: int) -> None:
    """Beim endgültigen Löschen eines Objekts die Zuordnungen beenden."""
    now = utcnow()
    for link in active_links(session, entity_type, entity_id).values():
        link.ended_at = now


# --- Stellen (dünne Hüllen, damit Aufrufer ``posting.tags`` direkt wieder lesen) ------------


def add_tags(
    session: Session, posting: JobPosting, names: list[str], *, origin: str = "manual"
) -> None:
    """Ergänzt Hashtags; bereits gesetzte bleiben unverändert."""
    link_tags(session, TagEntity.POSTING, posting.id, names, origin=origin)
    session.expire(posting, ["tag_links"])


def set_tags(session: Session, posting: JobPosting, names: list[str]) -> None:
    """Setzt genau diese Hashtags. Entfernte werden mit ``ended_at`` beendet, nicht gelöscht."""
    link_tags(session, TagEntity.POSTING, posting.id, names, replace=True)
    session.expire(posting, ["tag_links"])
