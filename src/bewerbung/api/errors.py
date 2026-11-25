"""Abbildung fachlicher Fehler auf HTTP-Antworten (einheitliches Fehlerformat)."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from bewerbung.domain.errors import (
    DomainError,
    DuplicatePostingError,
    InvalidTransitionError,
    LetterGenerationError,
    NotFoundError,
)
from bewerbung.sources.fetcher import FetchError

logger = logging.getLogger(__name__)


def _error(code: int, message: str, **extra: object) -> JSONResponse:
    return JSONResponse(status_code=code, content={"detail": message, **extra})


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def _not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return _error(status.HTTP_404_NOT_FOUND, str(exc))

    @app.exception_handler(DuplicatePostingError)
    async def _duplicate(_: Request, exc: DuplicatePostingError) -> JSONResponse:
        return _error(status.HTTP_409_CONFLICT, str(exc), existing_id=exc.existing_id)

    @app.exception_handler(InvalidTransitionError)
    async def _transition(_: Request, exc: InvalidTransitionError) -> JSONResponse:
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))

    @app.exception_handler(FetchError)
    async def _fetch(_: Request, exc: FetchError) -> JSONResponse:
        logger.info("Import fehlgeschlagen: %s", exc)
        return _error(status.HTTP_502_BAD_GATEWAY, str(exc))

    @app.exception_handler(LetterGenerationError)
    async def _letter(_: Request, exc: LetterGenerationError) -> JSONResponse:
        return _error(status.HTTP_502_BAD_GATEWAY, str(exc))

    @app.exception_handler(DomainError)
    async def _domain(_: Request, exc: DomainError) -> JSONResponse:
        return _error(status.HTTP_400_BAD_REQUEST, str(exc))

    @app.exception_handler(ValueError)
    async def _value(_: Request, exc: ValueError) -> JSONResponse:
        logger.debug("Ungültige Eingabe: %s", exc)
        return _error(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))
