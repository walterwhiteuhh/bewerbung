"""FastAPI-Abhängigkeiten. Engine und Registry hängen am ``app.state`` (testbar austauschbar)."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from bewerbung.db.session import session_scope
from bewerbung.sources import SourceRegistry


def get_session(request: Request) -> Iterator[Session]:
    yield from session_scope(request.app.state.session_factory)


def get_registry(request: Request) -> SourceRegistry:
    registry: SourceRegistry = request.app.state.source_registry
    return registry


SessionDep = Annotated[Session, Depends(get_session)]
RegistryDep = Annotated[SourceRegistry, Depends(get_registry)]
