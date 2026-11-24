"""Eigene Spaltentypen."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator


def utcnow() -> datetime:
    return datetime.now(UTC)


class UTCDateTime(TypeDecorator[datetime]):
    """Speichert immer UTC und liefert immer timezone-aware Werte zurück.

    SQLite kennt keine Zeitzonen; ohne diesen Typ kämen naive Datetimes zurück,
    was bei späteren Zeitreihen-Analysen zu stillen Verschiebungen führt.
    """

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("Naive datetime ist nicht erlaubt, bitte mit Zeitzone übergeben")
        return value.astimezone(UTC)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        assert isinstance(value, datetime)
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
