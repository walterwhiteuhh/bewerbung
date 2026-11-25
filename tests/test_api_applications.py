from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient


def _status(client: TestClient, app_id: int, status: str, **extra: object):
    return client.post(f"/api/applications/{app_id}/status", json={"status": status, **extra})


def test_status_history_is_append_only(client: TestClient, make_posting) -> None:
    app_id = make_posting()["application"]["id"]

    r1 = _status(client, app_id, "applied", note="Per Mail")
    assert r1.status_code == 200
    assert r1.json()["applied_at"] is not None
    applied_at = r1.json()["applied_at"]

    r2 = _status(client, app_id, "interview").json()
    assert r2["current_status"] == "interview"
    assert r2["applied_at"] == applied_at  # bleibt beim ersten Bewerbungszeitpunkt
    transitions = [(e["from_status"], e["to_status"]) for e in r2["events"]]
    assert transitions == [(None, "saved"), ("saved", "applied"), ("applied", "interview")]
    assert r2["events"][1]["note"] == "Per Mail"


def test_same_status_is_rejected(client: TestClient, make_posting) -> None:
    app_id = make_posting()["application"]["id"]
    assert _status(client, app_id, "saved").status_code == 422


def test_backdating_rules(client: TestClient, make_posting) -> None:
    app_id = make_posting()["application"]["id"]
    future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
    assert _status(client, app_id, "applied", occurred_at=future).status_code == 422
    past = (datetime.now(UTC) - timedelta(days=3)).isoformat()
    assert _status(client, app_id, "applied", occurred_at=past).status_code == 422  # vor Anlage


def test_notes_and_application_fields(client: TestClient, make_posting) -> None:
    app_id = make_posting()["application"]["id"]
    note = client.post(f"/api/applications/{app_id}/notes", json={"body": "  Gehalt erfragen "})
    assert note.status_code == 201
    assert note.json()["body"] == "Gehalt erfragen"

    resp = client.patch(
        f"/api/applications/{app_id}",
        json={
            "priority": 5,
            "contact_name": "Frau Müller",
            "follow_up_at": "2030-01-01T09:00:00+01:00",
        },
    )
    body = resp.json()
    assert body["priority"] == 5
    assert body["contact_name"] == "Frau Müller"
    assert body["follow_up_at"].startswith("2030-01-01T08:00:00")
    assert len(body["notes"]) == 1

    assert client.patch(f"/api/applications/{app_id}", json={"priority": 9}).status_code == 422


def test_stats(client: TestClient, make_posting) -> None:
    a = make_posting(url="https://www.linkedin.com/jobs/view/3912345678")["application"]["id"]
    b = make_posting()["application"]["id"]
    make_posting()
    _status(client, a, "applied")
    _status(client, a, "rejected")
    _status(client, b, "applied")

    stats = client.get("/api/stats").json()
    counts = {s["key"]: s["count"] for s in stats["by_status"]}
    assert stats["total"] == 3
    assert stats["active"] == 2
    assert counts["rejected"] == 1 and counts["applied"] == 1 and counts["saved"] == 1
    assert {s["key"]: s["count"] for s in stats["by_source"]} == {"manual": 2, "linkedin": 1}
    assert stats["response_rate"] == 0.5
    # 3 x "gemerkt" beim Anlegen + 3 Wechsel, alle innerhalb der letzten 7 Tage
    assert stats["activity_7d"] == 6
    assert stats["last_activity_at"] is not None
