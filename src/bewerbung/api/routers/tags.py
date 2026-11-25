"""Hashtags: Zählung, Verknüpfungen, Überblick und Zuordnung an Objekte."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, status

from bewerbung.api.deps import SessionDep
from bewerbung.domain.schemas import (
    EntityTagsUpdate,
    TagCount,
    TagOverview,
    TagRelationCreate,
    TagRelationRead,
)
from bewerbung.services import tag_graph

router = APIRouter()


@router.get("/tags", response_model=list[TagCount], tags=["tags"])
def list_tags(session: SessionDep) -> list[TagCount]:
    """Alle Hashtags mit Anzahl der (nicht archivierten) Stellen, häufigste zuerst."""
    return tag_graph.list_tags(session)


@router.get("/tags/relations", response_model=list[TagRelationRead], tags=["tags"])
def list_tag_relations(session: SessionDep) -> list[dict[str, Any]]:
    """Verknüpfungen zwischen Hashtags (Ober-/Unterbegriff, Synonym, verwandt)."""
    return tag_graph.list_relations(session)


@router.post(
    "/tags/relations",
    response_model=TagRelationRead,
    status_code=status.HTTP_201_CREATED,
    tags=["tags"],
)
def add_tag_relation(session: SessionDep, data: TagRelationCreate) -> dict[str, Any]:
    return tag_graph.add_relation(session, data.tag, data.related, data.kind)


@router.delete(
    "/tags/relations/{relation_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["tags"]
)
def remove_tag_relation(session: SessionDep, relation_id: int) -> None:
    tag_graph.remove_relation(session, relation_id)


@router.get("/tags/{name}/overview", response_model=TagOverview, tags=["tags"])
def tag_overview(session: SessionDep, name: str) -> dict[str, Any]:
    """Ein Hashtag über alle Objekte: Stellen, Firmen, Unterlagen, gespeicherte Suchen."""
    return tag_graph.overview(session, name)


@router.get("/tag-links/{entity_type}", response_model=dict[int, list[str]], tags=["tags"])
def tags_of_type(session: SessionDep, entity_type: str) -> dict[int, list[str]]:
    """Hashtags aller Objekte eines Typs (company, document, search_profile) auf einmal."""
    return tag_graph.tags_by_entity(session, entity_type)


@router.put("/tag-links/{entity_type}/{entity_id}", response_model=list[str], tags=["tags"])
def set_entity_tags(
    session: SessionDep, entity_type: str, entity_id: int, data: EntityTagsUpdate
) -> list[str]:
    return tag_graph.set_entity_tags(session, entity_type, entity_id, data.tags)
