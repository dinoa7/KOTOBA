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


def test_new_card_has_review_count_zero():
    _insert_card()

    due = client.get("/review/due").json()

    assert due[0]["review_count"] == 0


def test_grading_increments_review_count_regardless_of_pass_or_fail():
    card_id = _insert_card()

    resp1 = client.post("/review/grade", json={"card_id": card_id, "quality": 5})
    assert resp1.json()["review_count"] == 1

    resp2 = client.post("/review/grade", json={"card_id": card_id, "quality": 0})
    assert resp2.json()["review_count"] == 2

    with get_conn() as conn:
        row = conn.execute(
            "SELECT total_reviews FROM reviews WHERE card_id = ?", (card_id,)
        ).fetchone()
    assert row["total_reviews"] == 2


def test_cards_endpoint_still_works_without_review_count_column():
    # /cards doesn't join reviews at all — CardOut.from_row must not choke
    # on a row that simply doesn't have a review_count column.
    _insert_card()

    cards = client.get("/cards").json()

    assert cards[0]["review_count"] == 0
