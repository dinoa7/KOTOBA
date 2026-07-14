"""Shared helper for building tiny synthetic .apkg files in tests.
Not a test module itself — has no test_* functions, so pytest won't collect it.
"""

import io
import json
import sqlite3
import zipfile

MODEL_ID = "1"
FIELD_NAMES = ["Word", "Word Reading", "Word Meaning", "Sentence", "Sentence Meaning", "Sentence Audio", "Picture"]


def _build_collection_bytes(notes: list[dict]) -> bytes:
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE col (models TEXT)")
    models = {
        MODEL_ID: {
            "name": "Test Model",
            "flds": [{"name": n} for n in FIELD_NAMES],
            "tmpls": [{"name": "Card 1"}],
        }
    }
    conn.execute("INSERT INTO col (models) VALUES (?)", (json.dumps(models),))
    conn.execute("CREATE TABLE notes (id INTEGER PRIMARY KEY, mid TEXT, flds TEXT)")
    for i, n in enumerate(notes):
        flds = "\x1f".join(
            [
                n.get("word", ""),
                n.get("word_reading", ""),
                n.get("word_meaning", ""),
                n.get("sentence", ""),
                n.get("sentence_meaning", ""),
                n.get("sentence_audio", ""),
                n.get("picture", ""),
            ]
        )
        conn.execute("INSERT INTO notes (id, mid, flds) VALUES (?, ?, ?)", (1000 + i, MODEL_ID, flds))
    conn.commit()
    collection_bytes = conn.serialize()
    conn.close()
    return collection_bytes


def build_apkg(notes: list[dict], media: dict[str, bytes] | None = None) -> bytes:
    """notes: list of {word, word_reading, word_meaning, sentence, sentence_meaning, sentence_audio}
    media: {original_filename: raw_bytes}
    """
    media = media or {}
    collection_bytes = _build_collection_bytes(notes)
    media_map = {str(i): name for i, name in enumerate(media.keys())}

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("collection.anki21", collection_bytes)
        z.writestr("media", json.dumps(media_map))
        for i, (name, content) in enumerate(media.items()):
            z.writestr(str(i), content)
    return buf.getvalue()
