import io
import time
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app import anki_import
from app.config import AUDIO_DIR, EMBED_BATCH_SIZE, IMAGES_DIR, MOCK
from app.cohere_client import embed
from app.db import get_conn
from app.models import CardIn, CardOut, ImportResult
from app.vectors import get_store

router = APIRouter(prefix="/cards", tags=["cards"])

# Trial embed limit is 2,000 inputs/min (docs.cohere.com/docs/rate-limits),
# not a per-call cap. At EMBED_BATCH_SIZE=96, that's ~20 batches/min before
# a batch needs to wait for the next rolling window.
RATE_WINDOW_SECONDS = 60
MAX_BATCHES_PER_WINDOW = 2000 // EMBED_BATCH_SIZE


@router.get("", response_model=list[CardOut])
def list_cards():
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM cards ORDER BY id").fetchall()
    return [CardOut.from_row(r) for r in rows]


@router.post("", response_model=CardOut)
def create_card(card: CardIn):
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO cards (japanese, reading, english, tags, headword, "
            "word_reading, word_meaning, highlight, audio_path) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                card.japanese,
                card.reading,
                card.english,
                card.tags,
                card.headword,
                card.word_reading,
                card.word_meaning,
                card.highlight,
                card.audio_path,
            ),
        )
        card_id = cur.lastrowid
        conn.execute(
            "INSERT INTO reviews (card_id, due_date) VALUES (?, ?)",
            (card_id, date.today().isoformat()),
        )
        row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()

    embed_text = f"{card.japanese} ||| {card.english}"
    vectors = embed([embed_text], input_type="search_document")
    store = get_store()
    store.upsert(card_id, vectors[0])
    store.save()

    return CardOut.from_row(row)


@router.delete("/{card_id}")
def delete_card(card_id: int):
    with get_conn() as conn:
        conn.execute("DELETE FROM review_log WHERE card_id = ?", (card_id,))
        conn.execute("DELETE FROM reviews WHERE card_id = ?", (card_id,))
        cur = conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="card not found")
    return {"deleted": card_id}


def _parse_apkg_rows(raw_bytes: bytes, deck_tag: str) -> list[dict]:
    notes = anki_import.parse_apkg(io.BytesIO(raw_bytes), AUDIO_DIR, IMAGES_DIR)
    return [
        {
            "japanese": n.japanese,
            "reading": n.reading,
            "english": n.english,
            "tags": deck_tag,
            "headword": n.headword,
            "word_reading": n.word_reading,
            "word_meaning": n.word_meaning,
            "highlight": n.highlight,
            "audio_path": n.audio_path,
            "image_path": n.image_path,
        }
        for n in notes
    ]


def _insert_batch(rows: list[dict]) -> list[int]:
    with get_conn() as conn:
        ids = []
        for r in rows:
            cur = conn.execute(
                "INSERT INTO cards (japanese, reading, english, tags, headword, "
                "word_reading, word_meaning, highlight, audio_path, image_path) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    r["japanese"],
                    r["reading"],
                    r["english"],
                    r["tags"],
                    r["headword"],
                    r["word_reading"],
                    r["word_meaning"],
                    r["highlight"],
                    r["audio_path"],
                    r["image_path"],
                ),
            )
            ids.append(cur.lastrowid)
            conn.execute(
                "INSERT INTO reviews (card_id, due_date) VALUES (?, ?)",
                (cur.lastrowid, date.today().isoformat()),
            )
    return ids


async def _do_import(new_rows: list[dict], skipped: int) -> ImportResult:
    if not new_rows:
        return ImportResult(imported=0, skipped_duplicates=skipped, embed_calls=0)

    # Embed each batch BEFORE inserting its cards, and save the vector store
    # after every batch (not just at the end). If Cohere fails partway
    # through a large import, everything up to that point is already fully
    # embedded and persisted, and the rows that never got embedded were
    # never inserted either — so simply re-running the import later picks
    # up exactly where it left off, instead of those cards being stuck in
    # the DB forever with no vector (and un-retryable, since a re-import
    # would just skip them as duplicates).
    store = get_store()
    imported = 0
    embed_calls = 0
    batches_this_window = 0
    window_start = time.monotonic()
    try:
        for start in range(0, len(new_rows), EMBED_BATCH_SIZE):
            if not MOCK and batches_this_window >= MAX_BATCHES_PER_WINDOW:
                elapsed = time.monotonic() - window_start
                if elapsed < RATE_WINDOW_SECONDS:
                    time.sleep(RATE_WINDOW_SECONDS - elapsed)
                window_start = time.monotonic()
                batches_this_window = 0

            batch_rows = new_rows[start : start + EMBED_BATCH_SIZE]
            batch_texts = [f"{r['japanese']} ||| {r['english']}" for r in batch_rows]
            vectors = embed(batch_texts, input_type="search_document")
            embed_calls += 1
            batches_this_window += 1

            batch_ids = _insert_batch(batch_rows)
            for card_id, vec in zip(batch_ids, vectors):
                store.upsert(card_id, vec)
            store.save()
            imported += len(batch_rows)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=(
                f"Cohere API error during import: {e}. {imported} of {len(new_rows)} new "
                "cards were imported and embedded before the failure; re-run the import "
                "to pick up the rest — already-imported cards will be skipped as duplicates."
            ),
        ) from e

    return ImportResult(imported=imported, skipped_duplicates=skipped, embed_calls=embed_calls)


@router.post("/import", response_model=ImportResult)
async def import_cards(file: UploadFile):
    raw = await file.read()
    filename = file.filename or ""

    if not filename.lower().endswith(".apkg"):
        raise HTTPException(status_code=400, detail="Only .apkg files are supported for import")

    deck_tag = Path(filename).stem.lower().replace(" ", "-")
    parsed = _parse_apkg_rows(raw, deck_tag)

    # Dedup by (sentence, meaning, headword), not just (sentence, meaning):
    # sentence-per-word decks reuse one sentence for several target words
    # (あの<b>人</b>はいい人です vs あの人は<b>いい</b>人です), and those are
    # distinct cards, not duplicates.
    with get_conn() as conn:
        existing = {
            (r["japanese"], r["english"], r["headword"] or ""): dict(r)
            for r in conn.execute(
                "SELECT id, japanese, english, headword, word_reading, word_meaning, highlight, image_path FROM cards"
            ).fetchall()
        }

    new_rows = []
    backfill = []
    for r in parsed:
        match = existing.get((r["japanese"], r["english"], r["headword"]))
        if match is None:
            new_rows.append(r)
        elif (
            (r["word_reading"] and not match["word_reading"])
            or (r["word_meaning"] and not match["word_meaning"])
            or (r["highlight"] and not match["highlight"])
            or (r["image_path"] and not match["image_path"])
        ):
            backfill.append((r, match["id"]))
    skipped = len(parsed) - len(new_rows)

    # Cards imported before word/image fields existed get them filled in on
    # re-import — an UPDATE only, so it costs zero embed calls and never
    # touches SRS state.
    if backfill:
        with get_conn() as conn:
            for r, card_id in backfill:
                conn.execute(
                    "UPDATE cards SET word_reading = ?, word_meaning = ?, highlight = ?, image_path = ? WHERE id = ?",
                    (r["word_reading"], r["word_meaning"], r["highlight"], r["image_path"], card_id),
                )

    return await _do_import(new_rows, skipped)
