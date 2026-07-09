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


def test_search_dedupes_cards_sharing_the_same_example_sentence():
    # Same real-deck pattern as the confusions bug: two notes drilling
    # different headwords off one shared example sentence.
    id_a = _insert_card("あの人はいい人です。", "That person is a good person.", "いい")
    id_b = _insert_card("あの人はいい人です。", "That person is a good person.", "人")
    id_c = _insert_card("今日は天気がいいですね。", "The weather is nice today.", "天気")

    # MOCK-mode embeddings are 16-dim (see cohere_client._mock_embedding);
    # vectors must match that shape for cosine similarity to be computable.
    store = get_store()
    store.upsert(id_a, [1.0] + [0.0] * 15)
    store.upsert(id_b, [1.0] + [0.0] * 15)
    store.upsert(id_c, [0.9, 0.1] + [0.0] * 14)
    store.save()

    results = client.get("/search", params={"q": "good"}).json()

    sentences = [r["card"]["japanese"] for r in results]
    assert len(sentences) == len(set(sentences))
