from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from bewerbung.config import Settings
from bewerbung.main import create_app


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    # Echte Datei-DB + echte Migrationen: testet das Schema so, wie es produktiv entsteht.
    return Settings(
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}", log_level="WARNING"
    )


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def make_posting(client: TestClient):
    def _make(**overrides: object) -> dict:
        payload: dict[str, object] = {"title": "Data Scientist", "company_name": "ACME GmbH"}
        payload.update(overrides)
        resp = client.post("/api/postings", json=payload)
        assert resp.status_code == 201, resp.text
        return resp.json()

    return _make
