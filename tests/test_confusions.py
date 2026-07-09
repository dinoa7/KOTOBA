from fastapi.testclient import TestClient

from app.db import get_conn
from app.main import app
from app.vectors import get_store

client = TestClient(app)


def _insert_card(japanese, english, headword=""):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO cards (japanese, english, headword) VALUES (?, ?, ?)",
            (japanese, english, headword),
        )
        card_id = cur.lastrowid
        conn.execute(
            "INSERT INTO reviews (card_id, due_date) VALUES (?, '2026-01-01')",
            (card_id,),
        )
    return card_id


def test_identical_sentence_pairs_are_excluded_from_confusions():
    # Two notes drilling different headwords off the same example sentence —
    # a common real-deck pattern (§ the Kaishi bug). Same text -> same
    # embedding -> similarity ~1.0, but this isn't a real "confusion".
    id_a = _insert_card("今朝は早く家を出ました。", "I left early this morning.", "今朝")
    id_b = _insert_card("今朝は早く家を出ました。", "I left early this morning.", "出る")

    store = get_store()
    store.upsert(id_a, [1.0, 0.0])
    store.upsert(id_b, [1.0, 0.0])
    store.save()

    results = client.get("/confusions").json()

    assert all(p["card_a"]["japanese"] != p["card_b"]["japanese"] for p in results)


def test_genuinely_similar_distinct_sentences_are_surfaced():
    id_a = _insert_card("男の子たちがサッカーをしている。", "The boys are playing soccer.", "男の子")
    id_b = _insert_card("少年たちがサッカーをしている。", "The boys are playing soccer.", "少年")

    store = get_store()
    store.upsert(id_a, [1.0, 0.01])
    store.upsert(id_b, [0.99, 0.02])
    store.save()

    results = client.get("/confusions").json()

    pairs = {(p["card_a"]["id"], p["card_b"]["id"]) for p in results}
    assert (id_a, id_b) in pairs or (id_b, id_a) in pairs
