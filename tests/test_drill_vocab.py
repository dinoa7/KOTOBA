import pytest
from fastapi.testclient import TestClient

from app.db import get_conn
from app.drill_service import NoKnownVocabularyError, generate_drill, known_vocabulary
from app.main import app

client = TestClient(app)


def _insert_card(japanese, english, headword, repetitions):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO cards (japanese, english, headword) VALUES (?, ?, ?)",
            (japanese, english, headword),
        )
        card_id = cur.lastrowid
        conn.execute(
            "INSERT INTO reviews (card_id, repetitions, due_date) VALUES (?, ?, '2026-01-01')",
            (card_id, repetitions),
        )


def test_known_vocabulary_returns_headword_not_full_sentence():
    _insert_card("パンを食べる。", "I eat bread.", "食べる", repetitions=3)

    vocab = known_vocabulary()

    assert vocab == ["食べる"]


def test_known_vocabulary_falls_back_to_japanese_when_no_headword():
    _insert_card("こんにちは", "hello", "", repetitions=2)

    vocab = known_vocabulary()

    assert vocab == ["こんにちは"]


def test_known_vocabulary_excludes_cards_below_repetition_threshold():
    _insert_card("食べる", "to eat", "食べる", repetitions=1)

    vocab = known_vocabulary()

    assert vocab == []


def test_generate_drill_raises_clear_error_instead_of_calling_api_with_no_vocab():
    # Fresh import, nothing reviewed yet -> known_vocabulary() is empty.
    # Command A can't write a sentence with zero permitted words anyway
    # (it just returns an empty array after a real ~15s call) — fail fast
    # instead, before spending an API call on a guaranteed-empty response.
    with pytest.raises(NoKnownVocabularyError):
        generate_drill("te-form", 3)


def test_drill_endpoint_returns_400_with_clear_message_when_no_known_vocab():
    resp = client.post("/drill", json={"grammar_point": "te-form", "count": 3})

    assert resp.status_code == 400
    assert "reviewed" in resp.json()["detail"]
