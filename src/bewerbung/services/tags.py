"""Hashtags an Stellen setzen, ergänzen und auflisten."""

from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.orm import Session

from bewerbung.db.models import JobPosting, PostingTag, Tag
from bewerbung.db.types import utcnow
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


def _active_links(posting: JobPosting) -> dict[int, PostingTag]:
    return {link.tag_id: link for link in posting.tag_links if link.removed_at is None}


def add_tags(
    session: Session, posting: JobPosting, names: list[str], *, origin: str = "manual"
) -> None:
    """Ergänzt Hashtags; bereits gesetzte bleiben unverändert."""
    active = _active_links(posting)
    for tag in get_or_create_tags(session, names):
        if tag.id not in active:
            posting.tag_links.append(PostingTag(tag=tag, origin=origin))
    session.flush()


def set_tags(session: Session, posting: JobPosting, names: list[str]) -> None:
    """Setzt genau diese Hashtags. Entfernte werden mit ``removed_at`` beendet, nicht gelöscht."""
    tags = get_or_create_tags(session, names)
    wanted_ids = {t.id for t in tags}
    now = utcnow()
    for tag_id, link in _active_links(posting).items():
        if tag_id not in wanted_ids:
            link.removed_at = now
    add_tags(session, posting, [t.name for t in tags])
