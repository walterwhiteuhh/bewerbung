"""Startpunkt: ``uv run bewerbung`` oder ``python -m bewerbung``."""

from __future__ import annotations

import uvicorn

from bewerbung.config import get_settings


def main() -> None:
    settings = get_settings()
    uvicorn.run(
        "bewerbung.main:create_app",
        factory=True,
        host=settings.host,
        port=settings.port,
        log_config=None,
    )


if __name__ == "__main__":
    main()
