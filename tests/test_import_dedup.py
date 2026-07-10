from fastapi.testclient import TestClient

from app.main import app
from tests._apkg_fixtures import build_apkg

client = TestClient(app)

DECK_BYTES = build_apkg(
    [
        {
            "word": "映画",
            "word_meaning": "movie",
            "sentence": "昨日、映画を見ました。",
            "sentence_meaning": "I watched a movie yesterday.",
        }
    ]
)


def _upload(apkg_bytes: bytes, filename: str = "deck.apkg"):
    return client.post(
        "/cards/import",
        files={"file": (filename, apkg_bytes, "application/octet-stream")},
    )


def test_import_inserts_new_cards():
    resp = _upload(DECK_BYTES)
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 1
    assert data["skipped_duplicates"] == 0

    cards = client.get("/cards").json()
    assert len(cards) == 1
    assert cards[0]["japanese"] == "昨日、映画を見ました。"


def test_reimporting_same_deck_skips_duplicates():
    _upload(DECK_BYTES)
    resp = _upload(DECK_BYTES)
    data = resp.json()

    assert data["imported"] == 0
    assert data["skipped_duplicates"] == 1

    cards = client.get("/cards").json()
    assert len(cards) == 1


def test_import_embeds_and_populates_vector_store():
    _upload(DECK_BYTES)
    results = client.get("/search", params={"q": "movie"}).json()
    assert len(results) == 1


def test_non_apkg_upload_is_rejected():
    resp = client.post(
        "/cards/import",
        files={"file": ("deck.csv", b"japanese,reading,english,tags\n", "text/csv")},
    )
    assert resp.status_code == 400

    cards = client.get("/cards").json()
    assert len(cards) == 0


def test_apkg_import_uses_sentence_as_japanese_and_tags_by_deck_name():
    apkg_bytes = build_apkg(
        [
            {
                "word": "食べる",
                "word_meaning": "to eat",
                "sentence": "パンを食べる。",
                "sentence_meaning": "I eat bread.",
                "sentence_audio": "[sound:taberu.mp3]",
            }
        ],
        {"taberu.mp3": b"FAKE_AUDIO"},
    )

    resp = client.post("/cards/import", files={"file": ("My Deck.apkg", apkg_bytes, "application/octet-stream")})
    assert resp.status_code == 200
    data = resp.json()
    assert data["imported"] == 1

    cards = client.get("/cards").json()
    assert cards[0]["japanese"] == "パンを食べる。"
    assert cards[0]["headword"] == "食べる"
    assert cards[0]["tags"] == "my-deck"
    assert cards[0]["audio_path"] is not None
