"""Fachliche Fehler, unabhängig von HTTP. Die API bildet sie auf Statuscodes ab."""

from __future__ import annotations


class DomainError(Exception):
    """Basisklasse für erwartbare Fehler der Geschäftslogik."""


class NotFoundError(DomainError):
    def __init__(self, entity: str, entity_id: int | str) -> None:
        super().__init__(f"{entity} {entity_id} nicht gefunden")
        self.entity = entity
        self.entity_id = entity_id


class DuplicatePostingError(DomainError):
    def __init__(self, existing_id: int) -> None:
        super().__init__(f"Diese Stellenanzeige existiert bereits (ID {existing_id})")
        self.existing_id = existing_id


class InvalidTransitionError(DomainError):
    pass


class LetterGenerationError(DomainError):
    """Der Textgenerator (z. B. Claude-API) ist fehlgeschlagen."""


class DuplicateDocumentError(DomainError):
    def __init__(self, existing_id: int) -> None:
        super().__init__(f"Diese Datei ist schon hochgeladen (Dokument {existing_id})")
        self.existing_id = existing_id
