"""Schema-Qualität: Labels, Historie, abgeleitete Felder, Sichten und Integritätsregeln."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import closing
from pathlib import Path

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from bewerbung.config import Settings
from bewerbung.db.migrate import alembic_config
from tests.test_documents import make_pdf, upload


def _db(settings: Settings) -> sqlite3.Connection:
    return sqlite3.connect(settings.database_url.removeprefix("sqlite:///"))


def _rows(settings: Settings, sql: str, *args: object) -> list[tuple]:
    with closing(_db(settings)) as con:
        return con.execute(sql, args).fetchall()


def _status(client: TestClient, app_id: int, status: str, **extra: object):
    return client.post(f"/api/applications/{app_id}/status", json={"status": status, **extra})


# --- Labels ------------------------------------------------------------------------------


def test_offer_and_rejection_labels_are_stored(client: TestClient, make_posting) -> None:
    app_id = make_posting()["application"]["id"]
    _status(client, app_id, "applied")
    offer = _status(client, app_id, "offer", offered_salary=65000, offered_currency="eur")
    assert offer.status_code == 200
    ev = offer.json()["events"][-1]
    assert (ev["offered_salary"], ev["offered_currency"]) == (65000, "EUR")

    rej = _status(client, app_id, "rejected", reason_code="salary_mismatch")
    assert rej.json()["events"][-1]["reason_code"] == "salary_mismatch"


def test_labels_are_validated(client: TestClient, make_posting) -> None:
    app_id = make_posting()["application"]["id"]
    assert _status(client, app_id, "applied", reason_code="other").status_code == 422
    assert _status(client, app_id, "interview", offered_salary=1).status_code == 422
    assert _status(client, app_id, "rejected", reason_code="erfunden").status_code == 422
    assert _status(client, app_id, "offer", offered_salary=-5).status_code == 422


# --- Profil-Verlauf --------------------------------------------------------------------


def test_profile_versions_only_on_change_and_linked_to_application(
    client: TestClient, settings: Settings, make_posting
) -> None:
    client.put("/api/profile", json={"full_name": "Max", "skills": ["Python"]})
    client.put("/api/profile", json={"full_name": "Max", "skills": ["Python"]})  # unverändert
    assert _rows(settings, "SELECT COUNT(*) FROM applicant_profile_versions") == [(1,)]

    app_id = make_posting()["application"]["id"]
    _status(client, app_id, "applied")  # Stand v1
    client.put("/api/profile", json={"full_name": "Max", "skills": ["Python", "SQL"]})
    app2 = make_posting(title="Zweite")["application"]["id"]
    _status(client, app2, "applied")  # Stand v2

    pairs = dict(_rows(settings, "SELECT id, profile_version_id FROM applications"))
    assert pairs[app_id] != pairs[app2]
    snap = _rows(
        settings,
        "SELECT json_extract(snapshot, '$.skills') FROM applicant_profile_versions ORDER BY id",
    )
    assert snap == [('["Python"]',), ('["Python","SQL"]',)]


def test_saved_posting_has_no_profile_version(
    client: TestClient, settings: Settings, make_posting
) -> None:
    client.put("/api/profile", json={"full_name": "Max"})
    make_posting()
    assert _rows(settings, "SELECT profile_version_id FROM applications") == [(None,)]


# --- Haupt-Lebenslauf --------------------------------------------------------------------


def test_primary_cv_periods_are_tracked(client: TestClient, settings: Settings) -> None:
    a = upload(client, "a.pdf", make_pdf("Erster Lebenslauf"), kind="lebenslauf").json()
    b = upload(client, "b.pdf", make_pdf("Zweiter Lebenslauf"), kind="lebenslauf").json()
    client.patch(f"/api/documents/{b['id']}", json={"is_primary": True})

    rows = _rows(
        settings,
        "SELECT document_id, ended_at IS NULL FROM document_primary_periods ORDER BY id",
    )
    assert rows == [(a["id"], 0), (b["id"], 1)]

    client.post(f"/api/documents/{b['id']}/archive")
    assert _rows(
        settings, "SELECT COUNT(*) FROM document_primary_periods WHERE ended_at IS NULL"
    ) == [(0,)]


# --- Abgeleitete Felder an der Stelle ---------------------------------------------------


def test_posting_gets_title_key_and_place(
    client: TestClient, settings: Settings, make_posting
) -> None:
    make_posting(title="Data Engineer (m/w/d)", location="20095 Hamburg, Deutschland")
    row = _rows(settings, "SELECT title_key, city, postal_code FROM job_postings")[0]
    assert row == ("data engineer", "Hamburg", "20095")

    pid = _rows(settings, "SELECT id FROM job_postings")[0][0]
    client.patch(f"/api/postings/{pid}", json={"title": "ML Engineer", "location": "Berlin"})
    row = _rows(settings, "SELECT title_key, city, postal_code FROM job_postings")[0]
    assert row == ("ml engineer", "Berlin", None)


# --- Sichten und Integrität -----------------------------------------------------------


def test_status_duration_view(client: TestClient, settings: Settings, make_posting) -> None:
    app_id = make_posting()["application"]["id"]
    _status(client, app_id, "applied")
    _status(client, app_id, "interview")
    with closing(_db(settings)) as con, con:  # feste Zeitpunkte: 2 Tage in "applied"
        for status, ts in (
            ("saved", "2026-10-30 10:00:00.000000"),
            ("applied", "2026-11-01 10:00:00.000000"),
            ("interview", "2026-11-03 10:00:00.000000"),
        ):
            con.execute(
                "UPDATE application_status_events SET occurred_at = ? WHERE to_status = ?",
                (ts, status),
            )
    rows = _rows(
        settings,
        "SELECT status, ROUND(seconds_in_status) FROM v_status_durations "
        "WHERE application_id = ? AND status IN ('applied', 'interview') ORDER BY entered_at",
        app_id,
    )
    assert rows == [("applied", 172800.0), ("interview", None)]  # interview ist offen


def test_projection_matches_events(client: TestClient, settings: Settings, make_posting) -> None:
    app_id = make_posting()["application"]["id"]
    _status(client, app_id, "applied")
    assert _rows(settings, "SELECT * FROM v_application_status_check") == []
    with closing(_db(settings)) as con, con:
        con.execute("UPDATE applications SET current_status = 'offer'")
    assert _rows(
        settings, "SELECT projected_status, event_status FROM v_application_status_check"
    ) == [("offer", "applied")]


def test_tag_assignments_view_unifies_both_tables(
    client: TestClient, settings: Settings, make_posting
) -> None:
    make_posting(company_name="Acme", tags=["Python"])
    cid = _rows(settings, "SELECT id FROM companies")[0][0]
    client.put(f"/api/tag-links/company/{cid}", json={"tags": ["Python", "Remote"]})
    rows = _rows(
        settings,
        "SELECT entity_type, tag_key FROM v_tag_assignments WHERE removed_at IS NULL "
        "ORDER BY entity_type, tag_key",
    )
    assert rows == [("company", "python"), ("company", "remote"), ("posting", "python")]


def test_hard_delete_ends_tag_links_and_no_orphans(
    client: TestClient, settings: Settings, make_posting
) -> None:
    make_posting(company_name="Acme")
    cid = _rows(settings, "SELECT id FROM companies")[0][0]
    client.put(f"/api/tag-links/company/{cid}", json={"tags": ["Python"]})
    with closing(_db(settings)) as con, con:
        con.execute("DELETE FROM companies WHERE id = ?", (cid,))
    assert _rows(settings, "SELECT * FROM v_orphan_tag_links") == []
    assert _rows(settings, "SELECT removed_at IS NOT NULL FROM tag_links") == [(1,)]


def test_tag_link_entity_type_is_constrained(client: TestClient, settings: Settings) -> None:
    with closing(_db(settings)) as con:
        con.execute("INSERT INTO tags (name, key, created_at, updated_at) VALUES ('x','x',0,0)")
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(
                "INSERT INTO tag_links (entity_type, entity_id, tag_id, origin, added_at) "
                "VALUES ('quatsch', 1, 1, 'manual', 0)"
            )


# --- Migration mit Bestandsdaten ----------------------------------------------------------


@pytest.fixture
def old_db(tmp_path: Path) -> Iterator[tuple[str, object]]:
    url = f"sqlite:///{(tmp_path / 'm.db').as_posix()}"
    cfg = alembic_config(url)
    command.upgrade(cfg, "0013")
    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO job_postings (id, title, remote_type, salary_currency, source, created_at, updated_at) "
                "VALUES (1, 'Data Engineer (m/w/d)', 'unknown', 'EUR', 'linkedin', '2026-11-01 10:00:00', '2026-11-01 10:00:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO listings (posting_id, source, title, city, postal_code, lat, lon, remote_type, first_seen_at, last_seen_at, created_at, updated_at) "
                "VALUES (1, 'linkedin', 'x', 'Hamburg', '20095', 53.55, 9.99, 'unknown', '2026-11-01 10:00:00', '2026-11-01 10:00:00', '2026-11-01 10:00:00', '2026-11-01 10:00:00')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO applicant_profiles (id, full_name, skills, created_at, updated_at) "
                "VALUES (1, 'Max', '[\"Python\"]', '2026-11-01 10:00:00', '2026-11-01 10:00:00')"
            )
        )
    yield url, cfg
    engine.dispose()


def test_migration_backfills_existing_data_and_roundtrips(old_db: tuple[str, object]) -> None:
    url, cfg = old_db
    command.upgrade(cfg, "head")  # type: ignore[arg-type]
    engine = create_engine(url)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT title_key, city, postal_code, lat, lon FROM job_postings")
        ).one()
        assert tuple(row) == ("data engineer", "Hamburg", "20095", 53.55, 9.99)
        assert conn.execute(text("SELECT COUNT(*) FROM applicant_profile_versions")).scalar() == 1
    command.downgrade(cfg, "0013")  # type: ignore[arg-type]
    command.upgrade(cfg, "head")  # type: ignore[arg-type]
    engine.dispose()


def test_posting_tags_are_moved_into_tag_links_and_back(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'u.db').as_posix()}"
    cfg = alembic_config(url)
    command.upgrade(cfg, "0014")
    engine = create_engine(url)
    ts = "2026-11-01 10:00:00.000000"
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO job_postings (id, title, remote_type, salary_currency, source, created_at, updated_at) "
                f"VALUES (1, 'A', 'unknown', 'EUR', 'manual', '{ts}', '{ts}')"
            )
        )
        conn.execute(
            text(
                f"INSERT INTO tags (id, name, key, created_at, updated_at) VALUES (1, 'Python', 'python', '{ts}', '{ts}')"
            )
        )
        conn.execute(
            text(
                "INSERT INTO posting_tags (posting_id, tag_id, origin, added_at, removed_at) VALUES "
                f"(1, 1, 'manual', '{ts}', '2026-11-02 10:00:00.000000'), (1, 1, 'note', '{ts}', NULL)"
            )
        )
    command.upgrade(cfg, "head")
    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT entity_type, entity_id, origin, removed_at IS NULL FROM tag_links ORDER BY id"
            )
        ).all()
        assert [tuple(r) for r in rows] == [("posting", 1, "manual", 0), ("posting", 1, "note", 1)]
        assert conn.execute(text("SELECT COUNT(*) FROM v_orphan_tag_links")).scalar() == 0
    command.downgrade(cfg, "0014")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT COUNT(*) FROM posting_tags")).scalar() == 2
        assert conn.execute(text("SELECT COUNT(*) FROM tag_links")).scalar() == 0
    command.upgrade(cfg, "head")
    engine.dispose()
