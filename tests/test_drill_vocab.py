from app.db import get_conn
from app.drill_service import known_vocabulary


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
