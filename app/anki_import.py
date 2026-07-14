"""Parse Anki .apkg packages directly: notes plus their sentence audio.

KOTOBA's card model is sentence-first — the point of the app is to break
down and drill full sentences, not bare vocabulary. So `japanese` is the
note's example Sentence field (falling back to the headword if a note has
no sentence), while the standalone vocab word is kept separately as
`headword` — that's what the drill feature's known-vocabulary constraint
uses, since "you may only use these sentences" wouldn't make sense as a
generation constraint the way "you may only use these words" does.
"""

import json
import re
import shutil
import sqlite3
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path

CJK_RE = re.compile(r"[぀-ヿ一-鿿]")
HTML_TAG_RE = re.compile(r"<[^>]+>")
SOUND_REF_RE = re.compile(r"\[sound:([^\]]+)\]")
BOLD_OPEN_RE = re.compile(r"<(?:b|strong)>", re.IGNORECASE)
BOLD_CLOSE_RE = re.compile(r"</(?:b|strong)>", re.IGNORECASE)
IMG_SRC_RE = re.compile(r"<img[^>]+src=[\"']([^\"']+)[\"']", re.IGNORECASE)


@dataclass
class ParsedNote:
    japanese: str
    reading: str
    english: str
    headword: str
    word_reading: str
    word_meaning: str
    highlight: str | None
    audio_path: str | None
    image_path: str | None


def _clean_text(text: str) -> str:
    text = SOUND_REF_RE.sub("", text)
    text = HTML_TAG_RE.sub("", text)
    return text.strip()


def _extract_highlight(sentence_raw: str) -> str | None:
    """Preserve the deck's own target-word markup, stripping everything else.

    Anki renders note fields as raw HTML, so decks mark the target word by
    bolding it inside the Sentence field (あの<b>人</b>はいい人です。). That
    markup is the only reliable indicator of WHICH occurrence is the target —
    substring-matching the headword can't tell 人 from 人 in the example
    above — so keep it, normalized to literal <b></b> around the target.
    """
    text = SOUND_REF_RE.sub("", sentence_raw)
    text = BOLD_OPEN_RE.sub("\x00", text)
    text = BOLD_CLOSE_RE.sub("\x01", text)
    text = HTML_TAG_RE.sub("", text).strip()
    if "\x00" not in text or "\x01" not in text:
        return None
    return text.replace("\x00", "<b>").replace("\x01", "</b>")


def _extract_sound_filename(text: str) -> str | None:
    match = SOUND_REF_RE.search(text)
    return match.group(1) if match else None


def _extract_image_filename(text: str) -> str | None:
    match = IMG_SRC_RE.search(text)
    return match.group(1) if match else None


def _field_index(field_names: list[str], *candidates: str) -> int | None:
    lowered = [f.lower() for f in field_names]
    for cand in candidates:
        if cand.lower() in lowered:
            return lowered.index(cand.lower())
    return None


def _field(parts: list[str], idx: int | None) -> str:
    if idx is None or idx >= len(parts):
        return ""
    return parts[idx]


def parse_apkg(apkg_path: Path, audio_out_dir: Path, images_out_dir: Path | None = None) -> list[ParsedNote]:
    audio_out_dir.mkdir(parents=True, exist_ok=True)
    if images_out_dir is not None:
        images_out_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(apkg_path) as z:
        media_map = json.loads(z.read("media"))
        filename_to_member = {v: k for k, v in media_map.items()}

        member = "collection.anki21" if "collection.anki21" in z.namelist() else "collection.anki2"
        with tempfile.TemporaryDirectory() as tmp:
            z.extract(member, tmp)
            conn = sqlite3.connect(Path(tmp) / member)
            cur = conn.cursor()
            cur.execute("SELECT models FROM col")
            models = json.loads(cur.fetchone()[0])

            field_layout = {}
            for mid, model in models.items():
                names = [f["name"] for f in model["flds"]]
                field_layout[mid] = {
                    "word": _field_index(names, "Word", "Front", "Expression"),
                    "word_reading": _field_index(names, "Word Reading", "Reading"),
                    "word_meaning": _field_index(names, "Word Meaning", "Meaning", "Back"),
                    "sentence": _field_index(names, "Sentence"),
                    "sentence_meaning": _field_index(names, "Sentence Meaning"),
                    "sentence_furigana": _field_index(names, "Sentence Furigana"),
                    "sentence_audio": _field_index(names, "Sentence Audio"),
                    "picture": _field_index(names, "Picture", "Image"),
                }

            cur.execute("SELECT id, mid, flds FROM notes")
            note_rows = cur.fetchall()

            parsed: list[ParsedNote] = []
            for note_id, mid, flds in note_rows:
                layout = field_layout.get(str(mid))
                if layout is None:
                    continue
                parts = flds.split("\x1f")

                headword = _clean_text(_field(parts, layout["word"]))
                sentence_raw = _field(parts, layout["sentence"])
                sentence = _clean_text(sentence_raw)
                japanese = sentence or headword

                # The headword is the reliable "is this actually a vocab
                # note" signal — checking the sentence/notes text for any
                # single CJK character is too loose (e.g. a deck's English
                # description card mentioning "Kaishi (開始)" would pass).
                cjk_source = headword or japanese
                if not CJK_RE.search(cjk_source):
                    continue

                english = _clean_text(_field(parts, layout["sentence_meaning"])) or _clean_text(
                    _field(parts, layout["word_meaning"])
                )
                reading = _clean_text(_field(parts, layout["sentence_furigana"]))
                word_reading = _clean_text(_field(parts, layout["word_reading"]))
                word_meaning = _clean_text(_field(parts, layout["word_meaning"]))
                highlight = _extract_highlight(sentence_raw) if sentence else None

                audio_path = None
                sound_field = _field(parts, layout["sentence_audio"])
                sound_filename = _extract_sound_filename(sound_field)
                if sound_filename and sound_filename in filename_to_member:
                    member_name = filename_to_member[sound_filename]
                    ext = Path(sound_filename).suffix or ".mp3"
                    out_name = f"{note_id}{ext}"
                    with z.open(member_name) as src, open(audio_out_dir / out_name, "wb") as dst:
                        shutil.copyfileobj(src, dst)
                    audio_path = out_name

                image_path = None
                if images_out_dir is not None:
                    picture_field = _field(parts, layout["picture"])
                    image_filename = _extract_image_filename(picture_field)
                    if image_filename and image_filename in filename_to_member:
                        member_name = filename_to_member[image_filename]
                        ext = Path(image_filename).suffix or ".jpg"
                        out_name = f"{note_id}{ext}"
                        with z.open(member_name) as src, open(images_out_dir / out_name, "wb") as dst:
                            shutil.copyfileobj(src, dst)
                        image_path = out_name

                parsed.append(
                    ParsedNote(
                        japanese=japanese,
                        reading=reading,
                        english=english,
                        headword=headword,
                        word_reading=word_reading,
                        word_meaning=word_meaning,
                        highlight=highlight,
                        audio_path=audio_path,
                        image_path=image_path,
                    )
                )

            conn.close()

    return parsed
