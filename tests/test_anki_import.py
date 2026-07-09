import io

from app.anki_import import parse_apkg
from tests._apkg_fixtures import build_apkg


def test_parse_apkg_extracts_sentence_as_japanese_and_word_as_headword(tmp_path):
    notes = [
        {
            "word": "私",
            "word_reading": "わたし",
            "word_meaning": "I",
            "sentence": "<b>私</b>はアンです。",
            "sentence_meaning": "I am Ann.",
            "sentence_audio": "[sound:watashi.mp3]",
        }
    ]
    apkg_bytes = build_apkg(notes, {"watashi.mp3": b"FAKE_MP3_BYTES"})
    audio_dir = tmp_path / "audio"

    parsed = parse_apkg(io.BytesIO(apkg_bytes), audio_dir)

    assert len(parsed) == 1
    note = parsed[0]
    assert note.japanese == "私はアンです。"
    assert note.headword == "私"
    assert note.english == "I am Ann."
    assert note.audio_path is not None
    assert (audio_dir / note.audio_path).read_bytes() == b"FAKE_MP3_BYTES"


def test_parse_apkg_falls_back_to_headword_when_sentence_empty(tmp_path):
    notes = [{"word": "犬", "word_meaning": "dog", "sentence": "", "sentence_meaning": ""}]
    apkg_bytes = build_apkg(notes)

    parsed = parse_apkg(io.BytesIO(apkg_bytes), tmp_path / "audio")

    assert len(parsed) == 1
    assert parsed[0].japanese == "犬"
    assert parsed[0].english == "dog"
    assert parsed[0].audio_path is None


def test_parse_apkg_skips_notes_with_no_japanese_text(tmp_path):
    notes = [
        {"word": "Welcome to the deck!", "sentence": "", "sentence_meaning": "Good luck."},
        {"word": "猫", "sentence": "猫がいます。", "sentence_meaning": "There is a cat."},
    ]
    apkg_bytes = build_apkg(notes)

    parsed = parse_apkg(io.BytesIO(apkg_bytes), tmp_path / "audio")

    assert len(parsed) == 1
    assert parsed[0].japanese == "猫がいます。"


def test_parse_apkg_skips_english_note_with_incidental_kanji_in_sentence(tmp_path):
    """Regression: a deck's English intro/description card can mention a
    Japanese word in passing (e.g. "Kaishi (開始) is a vocabulary deck...").
    A single-CJK-character check on the sentence text alone would wrongly
    treat that as a real vocab note; the headword (non-Japanese here) is
    the reliable signal that this isn't one.
    """
    notes = [
        {
            "word": "Welcome to Kaishi 1.5k!",
            "sentence": "Kaishi (開始) is a modular Japanese vocabulary deck.",
            "sentence_meaning": "Good luck on your journey!",
        }
    ]
    apkg_bytes = build_apkg(notes)

    parsed = parse_apkg(io.BytesIO(apkg_bytes), tmp_path / "audio")

    assert parsed == []
