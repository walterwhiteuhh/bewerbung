"""Hashtags übergreifend: Verknüpfungen zwischen Tags und Tags an beliebigen Objekten.

Im Hintergrund erweitert der Graph Filter (``#ki`` findet auch ``#machine-learning``),
sichtbar bleibt nur, was der Nutzer gesetzt hat.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from bewerbung.db.models import (
    Company,
    Document,
    JobPosting,
    SearchProfile,
    Tag,
    TagLink,
    TagRelation,
)
from bewerbung.db.types import utcnow
from bewerbung.domain.enums import TagEntity
from bewerbung.domain.errors import DomainError, NotFoundError
from bewerbung.domain.schemas import TagCount
from bewerbung.domain.tags import tag_key
from bewerbung.services.tags import link_tags

logger = logging.getLogger(__name__)

ENTITY_MODELS: dict[str, Any] = {
    TagEntity.POSTING: JobPosting,
    TagEntity.COMPANY: Company,
    TagEntity.DOCUMENT: Document,
    TagEntity.SEARCH_PROFILE: SearchProfile,
}
KINDS = ("implies", "alias", "related")


# --- Graph ---------------------------------------------------------------------------


class Graph:
    """Aktive Verknüpfungen im Speicher (wenige Hundert Zeilen), alles über Tag-Schlüssel."""

    def __init__(self, session: Session) -> None:
        self.children: dict[str, set[str]] = defaultdict(set)  # Oberbegriff -> Unterbegriffe
        self.parents: dict[str, set[str]] = defaultdict(set)
        self.aliases: dict[str, set[str]] = defaultdict(set)
        self.related: dict[str, set[str]] = defaultdict(set)
        rows = session.execute(
            select(TagRelation.tag_key, TagRelation.related_key, TagRelation.kind).where(
                TagRelation.removed_at.is_(None)
            )
        )
        for a, b, kind in rows:
            if kind == "implies":
                self.children[b].add(a)
                self.parents[a].add(b)
            elif kind == "alias":
                self.aliases[a].add(b)
                self.aliases[b].add(a)
            else:
                self.related[a].add(b)
                self.related[b].add(a)

    def expand(self, key: str) -> set[str]:
        """Schlüssel samt Synonymen und allen Unterbegriffen (für Filter)."""
        seen: set[str] = set()
        todo = [key]
        while todo:
            cur = todo.pop()
            if cur in seen:
                continue
            seen.add(cur)
            todo += self.aliases.get(cur, set()) | self.children.get(cur, set())
        return seen

    def ancestors(self, key: str) -> set[str]:
        seen: set[str] = set()
        todo = list(self.parents.get(key, set()))
        while todo:
            cur = todo.pop()
            if cur not in seen:
                seen.add(cur)
                todo += self.parents.get(cur, set())
        return seen


def expand_filter_ids(
    session: Session, keys: list[str], graph: Graph | None = None
) -> list[set[int]]:
    """Je Hashtag die Menge gleichwertiger Tag-IDs; ohne Treffer in ``tags`` eine leere Menge."""
    graph = graph or Graph(session)
    expanded = [graph.expand(k) for k in keys]
    wanted = set().union(*expanded) if expanded else set()
    ids = dict(session.execute(select(Tag.key, Tag.id).where(Tag.key.in_(wanted))).all())
    return [{ids[k] for k in group if k in ids} for group in expanded]


def list_tags(session: Session) -> list[TagCount]:
    """Alle Hashtags mit Anzahl aktiver, nicht archivierter Stellen.

    Oberbegriffe aus den Verknüpfungen (z. B. ``frontend`` über ``react``) erscheinen
    zusätzlich mit der Zahl aller darunterliegenden Stellen und sind als ``derived`` markiert.
    """
    pairs = session.execute(
        select(Tag.key, Tag.name, TagLink.entity_id)
        .join(TagLink, TagLink.tag_id == Tag.id)
        .join(JobPosting, JobPosting.id == TagLink.entity_id)
        .where(
            TagLink.entity_type == TagEntity.POSTING,
            TagLink.removed_at.is_(None),
            JobPosting.archived_at.is_(None),
        )
    ).all()
    if not pairs:
        return []
    own: dict[str, set[int]] = {}
    names: dict[str, str] = {}
    for key, name, posting_id in pairs:
        own.setdefault(key, set()).add(posting_id)
        names[key] = name
    graph = Graph(session)
    candidates = set(own)
    for key in list(own):
        candidates |= graph.ancestors(key)
    out: list[TagCount] = []
    for key in candidates:
        postings: set[int] = set()
        for member in graph.expand(key):
            postings |= own.get(member, set())
        if postings:
            out.append(
                TagCount(name=names.get(key, key), count=len(postings), derived=key not in own)
            )
    out.sort(key=lambda t: (-t.count, t.name.casefold()))
    return out


# --- Tags an Objekten ------------------------------------------------------------------


def _check_entity(session: Session, entity_type: str, entity_id: int) -> None:
    model = ENTITY_MODELS.get(entity_type)
    if model is None:
        raise DomainError(f"Unbekannter Objekttyp: {entity_type}")
    if session.get(model, entity_id) is None:
        raise NotFoundError(entity_type, entity_id)


def entity_tags(session: Session, entity_type: str, entity_id: int) -> list[str]:
    _check_entity(session, entity_type, entity_id)
    return _names(session, entity_type, [entity_id]).get(entity_id, [])


def _names(session: Session, entity_type: str, ids: list[int] | None) -> dict[int, list[str]]:
    stmt = (
        select(TagLink.entity_id, Tag.name)
        .join(Tag, Tag.id == TagLink.tag_id)
        .where(TagLink.entity_type == entity_type, TagLink.removed_at.is_(None))
    )
    if ids is not None:
        stmt = stmt.where(TagLink.entity_id.in_(ids))
    out: dict[int, list[str]] = defaultdict(list)
    for entity_id, name in session.execute(stmt):
        out[entity_id].append(name)
    return {k: sorted(v, key=str.casefold) for k, v in out.items()}


def tags_by_entity(session: Session, entity_type: str) -> dict[int, list[str]]:
    """Alle Tags eines Objekttyps auf einmal (für Listen, ein Abruf statt einer je Zeile)."""
    if entity_type not in ENTITY_MODELS:
        raise DomainError(f"Unbekannter Objekttyp: {entity_type}")
    return _names(session, entity_type, None)


def set_entity_tags(
    session: Session, entity_type: str, entity_id: int, names: list[str], *, origin: str = "manual"
) -> list[str]:
    """Setzt genau diese Hashtags; entfernte behalten ``removed_at`` für die Historie."""
    _check_entity(session, entity_type, entity_id)
    tags = link_tags(session, entity_type, entity_id, names, origin=origin, replace=True)
    return sorted((t.name for t in tags), key=str.casefold)


# --- Verknüpfungen pflegen ---------------------------------------------------------------


def list_relations(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        select(
            TagRelation.id,
            TagRelation.tag_key,
            TagRelation.related_key,
            TagRelation.kind,
            TagRelation.origin,
        )
        .where(TagRelation.removed_at.is_(None))
        .order_by(TagRelation.related_key, TagRelation.tag_key)
    )
    return [{"id": i, "tag": x, "related": y, "kind": k, "origin": o} for i, x, y, k, o in rows]


def add_relation(session: Session, tag: str, related: str, kind: str) -> dict[str, Any]:
    if kind not in KINDS:
        raise DomainError(f"Art der Verknüpfung: {', '.join(KINDS)}")
    a, b = tag_key(tag), tag_key(related)
    if a == b:
        raise DomainError("Ein Hashtag lässt sich nicht mit sich selbst verknüpfen")
    graph = Graph(session)
    if kind == "implies" and (b in graph.expand(a) or a in graph.ancestors(b)):
        raise DomainError("Diese Verknüpfung würde einen Kreis erzeugen")
    existing = session.scalar(
        select(TagRelation).where(
            TagRelation.tag_key == a,
            TagRelation.related_key == b,
            TagRelation.kind == kind,
            TagRelation.removed_at.is_(None),
        )
    )
    rel = existing or TagRelation(tag_key=a, related_key=b, kind=kind, origin="manual")
    if existing is None:
        session.add(rel)
        session.flush()
    return {"id": rel.id, "tag": a, "related": b, "kind": kind, "origin": rel.origin}


def remove_relation(session: Session, relation_id: int) -> None:
    rel = session.get(TagRelation, relation_id)
    if rel is None or rel.removed_at is not None:
        raise NotFoundError("Verknüpfung", relation_id)
    rel.removed_at = utcnow()
    session.flush()


# --- Übergreifende Sicht -------------------------------------------------------------------


def related_tags(session: Session, key: str, limit: int = 8) -> list[str]:
    """Verwandte Hashtags: gepflegte Hinweise zuerst, dann Tags, die oft zusammen auftreten."""
    key = tag_key(key)
    graph = Graph(session)
    own = graph.expand(key)
    hinted = (graph.related.get(key, set()) | graph.parents.get(key, set())) - own
    own_ids = {i for (i,) in session.execute(select(Tag.id).where(Tag.key.in_(own)))}
    other = aliased(TagLink)
    co = session.execute(
        select(other.tag_id, func.count())
        .join(
            TagLink,
            (TagLink.entity_type == other.entity_type) & (TagLink.entity_id == other.entity_id),
        )
        .where(
            TagLink.entity_type == TagEntity.POSTING,
            TagLink.tag_id.in_(own_ids or {-1}),
            TagLink.removed_at.is_(None),
            other.removed_at.is_(None),
            other.tag_id.not_in(own_ids or {-1}),
        )
        .group_by(other.tag_id)
        .order_by(func.count().desc())
        .limit(limit)
    ).all()
    co_names = dict(
        session.execute(select(Tag.id, Tag.name).where(Tag.id.in_([i for i, _ in co]))).all()
    )
    out = sorted(hinted) + [co_names[i] for i, _ in co if i in co_names]
    seen: dict[str, str] = {}
    for name in out:
        seen.setdefault(name.casefold(), name)
    return list(seen.values())[:limit]


def overview(session: Session, key: str) -> dict[str, Any]:
    """Alles zu einem Hashtag über alle Objekttypen hinweg (inkl. Unter- und Synonym-Tags)."""
    key = tag_key(key)
    keys = Graph(session).expand(key)
    tags = session.execute(select(Tag.id, Tag.key, Tag.name).where(Tag.key.in_(keys))).all()
    ids = {i for i, _, _ in tags}
    if not ids and keys == {key}:
        raise NotFoundError("Hashtag", key)
    postings = session.execute(
        select(JobPosting.id, JobPosting.title)
        .join(
            TagLink,
            (TagLink.entity_id == JobPosting.id) & (TagLink.entity_type == TagEntity.POSTING),
        )
        .where(
            TagLink.tag_id.in_(ids or {-1}),
            TagLink.removed_at.is_(None),
            JobPosting.archived_at.is_(None),
        )
        .distinct()
        .order_by(JobPosting.id.desc())
    ).all()
    linked: dict[str, list[dict[str, Any]]] = {}
    for etype, model, label in (
        (TagEntity.COMPANY, Company, Company.name),
        (TagEntity.DOCUMENT, Document, Document.title),
        (TagEntity.SEARCH_PROFILE, SearchProfile, SearchProfile.name),
    ):
        rows = session.execute(
            select(model.id, label)
            .join(TagLink, (TagLink.entity_id == model.id) & (TagLink.entity_type == etype))
            .where(TagLink.tag_id.in_(ids or {-1}), TagLink.removed_at.is_(None))
            .distinct()
        ).all()
        linked[etype.value] = [{"id": i, "label": n} for i, n in rows]
    # Firmen auch über ihre Stellen: wer Stellen mit dem Tag hat, gehört dazu.
    via_postings = session.execute(
        select(Company.id, Company.name)
        .join(JobPosting, JobPosting.company_id == Company.id)
        .where(JobPosting.id.in_([p for p, _ in postings] or [0]))
        .distinct()
    ).all()
    seen = {c["id"] for c in linked["company"]}
    linked["company"] += [{"id": i, "label": n} for i, n in via_postings if i not in seen]
    names = {k: n for _, k, n in tags}
    return {
        "tag": names.get(key, key),
        "includes": sorted((names.get(k, k) for k in keys), key=str.casefold),
        "related": related_tags(session, key),
        "postings": [{"id": i, "label": t} for i, t in postings],
        **linked,
    }
