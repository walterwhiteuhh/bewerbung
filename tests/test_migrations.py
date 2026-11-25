from __future__ import annotations

from pathlib import Path

from alembic import command
from sqlalchemy import create_engine, text

from bewerbung.db.migrate import alembic_config


def test_upgrade_migrates_existing_postings_to_listings(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    cfg = alembic_config(url)
    command.upgrade(cfg, "0001")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO job_postings (id, title, remote_type, salary_currency, source, external_id, url, created_at, updated_at) "
                "VALUES (1, 'Alt', 'unknown', 'EUR', 'linkedin', '123', 'https://linkedin.com/jobs/view/123', '2026-11-01 10:00:00', '2026-11-01 10:00:00'),"
                "       (2, 'Manuell', 'unknown', 'EUR', 'manual', NULL, NULL, '2026-11-01 10:00:00', '2026-11-01 10:00:00')"
            )
        )
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        rows = conn.execute(text("SELECT posting_id, source, external_id FROM listings")).all()
    assert rows == [(1, "linkedin", "123")]
    command.downgrade(cfg, "0001")
