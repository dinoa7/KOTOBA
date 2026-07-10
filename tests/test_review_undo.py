from datetime import date

from fastapi.testclient import TestClient

from app.db import get_conn
from app.main import app

client = TestClient(app)


def _insert_card(japanese="今日は良い天気です。", english="It's nice weather today."):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO cards (japanese, english) VALUES (?, ?)", (japanese, english)
        )
        card_id = cur.lastrowid
        conn.execute(
            "INSERT INTO reviews (card_id, due_date) VALUES (?, ?)",
            (card_id, date.today().isoformat()),
        )
    return card_id


def test_undo_restores_prior_review_state():
    card_id = _insert_card()

    with get_conn() as conn:
        before = dict(
            conn.execute("SELECT * FROM reviews WHERE card_id = ?", (card_id,)).fetchone()
        )

    client.post("/review/grade", json={"card_id": card_id, "quality": 5})

    undo_resp = client.post("/review/undo")
    assert undo_resp.status_code == 200
    assert undo_resp.json()["card_id"] == card_id

    with get_conn() as conn:
        after = dict(
            conn.execute("SELECT * FROM reviews WHERE card_id = ?", (card_id,)).fetchone()
        )

    assert after == before


def test_undo_removes_entry_from_recent():
    card_id = _insert_card()
    client.post("/review/grade", json={"card_id": card_id, "quality": 5})

    recent_before = client.get("/review/recent").json()
    assert any(e["card"]["id"] == card_id for e in recent_before)

    client.post("/review/undo")

    recent_after = client.get("/review/recent").json()
    assert not any(e["card"]["id"] == card_id for e in recent_after)


def test_undo_with_nothing_to_undo_returns_404():
    with get_conn() as conn:
        conn.execute("DELETE FROM review_log")

    resp = client.post("/review/undo")
    assert resp.status_code == 404


def test_recent_reflects_most_recent_grade_not_undone_one():
    card_id = _insert_card()
    client.post("/review/grade", json={"card_id": card_id, "quality": 0})
    client.post("/review/grade", json={"card_id": card_id, "quality": 5})

    recent = client.get("/review/recent").json()
    entry = next(e for e in recent if e["card"]["id"] == card_id)
    assert entry["quality"] == 5


def test_deleting_graded_card_does_not_error():
    card_id = _insert_card()
    client.post("/review/grade", json={"card_id": card_id, "quality": 4})

    resp = client.delete(f"/cards/{card_id}")
    assert resp.status_code == 200
