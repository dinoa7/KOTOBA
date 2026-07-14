from datetime import date

from fastapi.testclient import TestClient

from app.db import get_conn
from app.main import app
from tests._apkg_fixtures import build_apkg

client = TestClient(app)


def _upload(apkg_bytes: bytes):
    return client.post(
        "/cards/import",
        files={"file": ("deck.apkg", apkg_bytes, "application/octet-stream")},
    )


def test_word_fields_and_highlight_markup_survive_import():
    deck = build_apkg(
        [
            {
                "word": "人",
                "word_reading": "ひと",
                "word_meaning": "person",
                "sentence": "あの<b>人</b>はいい人です。",
                "sentence_meaning": "That person is a good person.",
            }
        ]
    )

    resp = _upload(deck)
    assert resp.json()["imported"] == 1

    card = client.get("/cards").json()[0]
    assert card["japanese"] == "あの人はいい人です。"  # clean text, markup stripped
    assert card["highlight"] == "あの<b>人</b>はいい人です。"  # markup kept, occurrence preserved
    assert card["word_reading"] == "ひと"
    assert card["word_meaning"] == "person"


def test_same_sentence_different_headword_is_not_a_duplicate():
    deck = build_apkg(
        [
            {
                "word": "人",
                "word_meaning": "person",
                "sentence": "あの<b>人</b>はいい人です。",
                "sentence_meaning": "That person is a good person.",
            },
            {
                "word": "いい",
                "word_meaning": "good",
                "sentence": "あの人は<b>いい</b>人です。",
                "sentence_meaning": "That person is a good person.",
            },
        ]
    )

    resp = _upload(deck)
    data = resp.json()
    assert data["imported"] == 2
    assert data["skipped_duplicates"] == 0

    cards = client.get("/cards").json()
    assert len(cards) == 2
    # Both clean to the same japanese, but each highlights its own occurrence.
    highlights = {c["headword"]: c["highlight"] for c in cards}
    assert highlights["人"] == "あの<b>人</b>はいい人です。"
    assert highlights["いい"] == "あの人は<b>いい</b>人です。"

    # Re-importing the same deck now skips both as true duplicates.
    resp2 = _upload(deck)
    assert resp2.json()["imported"] == 0
    assert resp2.json()["skipped_duplicates"] == 2


def test_picture_field_is_extracted_and_served():
    deck = build_apkg(
        [
            {
                "word": "兄",
                "word_reading": "あに",
                "word_meaning": "older brother",
                "sentence": "これは<b>兄</b>のパソコンです。",
                "sentence_meaning": "This is my older brother's computer.",
                "picture": '<img src="ani.jpg">',
            }
        ],
        {"ani.jpg": b"FAKE_IMAGE_BYTES"},
    )

    resp = _upload(deck)
    assert resp.json()["imported"] == 1

    card = client.get("/cards").json()[0]
    assert card["image_path"] is not None

    img = client.get(f"/images/{card['image_path']}")
    assert img.status_code == 200
    assert img.content == b"FAKE_IMAGE_BYTES"


def test_note_without_picture_has_no_image_path():
    deck = build_apkg(
        [
            {
                "word": "人",
                "word_meaning": "person",
                "sentence": "あの<b>人</b>はいい人です。",
                "sentence_meaning": "That person is a good person.",
            }
        ]
    )

    _upload(deck)
    card = client.get("/cards").json()[0]
    assert card["image_path"] is None


def test_reimport_backfills_word_fields_without_new_cards():
    # A card imported before word fields existed: headword present, the rest empty.
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO cards (japanese, english, headword) VALUES (?, ?, ?)",
            ("あの人はいい人です。", "That person is a good person.", "人"),
        )
        conn.execute(
            "INSERT INTO reviews (card_id, due_date) VALUES (?, ?)",
            (cur.lastrowid, date.today().isoformat()),
        )

    deck = build_apkg(
        [
            {
                "word": "人",
                "word_reading": "ひと",
                "word_meaning": "person",
                "sentence": "あの<b>人</b>はいい人です。",
                "sentence_meaning": "That person is a good person.",
            }
        ]
    )

    resp = _upload(deck)
    data = resp.json()
    assert data["imported"] == 0
    assert data["skipped_duplicates"] == 1
    assert data["embed_calls"] == 0

    card = client.get("/cards").json()[0]
    assert card["word_meaning"] == "person"
    assert card["word_reading"] == "ひと"
    assert card["highlight"] == "あの<b>人</b>はいい人です。"
