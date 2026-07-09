import csv
import io
import time
from datetime import date
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app import anki_import
from app.config import AUDIO_DIR, EMBED_BATCH_SIZE, MOCK
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
            "INSERT INTO cards (japanese, reading, english, tags, headword, audio_path) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (card.japanese, card.reading, card.english, card.tags, card.headword, card.audio_path),
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
        conn.execute("DELETE FROM reviews WHERE card_id = ?", (card_id,))
        cur = conn.execute("DELETE FROM cards WHERE id = ?", (card_id,))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="card not found")
    return {"deleted": card_id}


def _parse_csv_rows(raw_text: str) -> list[dict]:
    """Accepts CSV/tab-delimited: japanese,reading,english,tags[,headword,audio_path]."""
    lines = [l for l in raw_text.splitlines() if l.strip() and not l.startswith("#")]
    if not lines:
        return []
    delimiter = "\t" if "\t" in lines[0] else ","
    reader = csv.reader(lines, delimiter=delimiter)
    rows = []
    for parts in reader:
        parts = [p.strip() for p in parts]
        if len(parts) < 2:
            continue
        japanese = parts[0]
        if japanese.lower() == "japanese":
            continue  # header row
        reading = parts[1] if len(parts) > 1 else ""
        english = parts[2] if len(parts) > 2 else (parts[1] if len(parts) == 2 else "")
        tags = parts[3] if len(parts) > 3 else ""
        headword = parts[4] if len(parts) > 4 else ""
        audio_path = parts[5] if len(parts) > 5 and parts[5] else None
        rows.append(
            {
                "japanese": japanese,
                "reading": reading,
                "english": english,
                "tags": tags,
                "headword": headword,
                "audio_path": audio_path,
            }
        )
    return rows


def _parse_apkg_rows(raw_bytes: bytes, deck_tag: str) -> list[dict]:
    notes = anki_import.parse_apkg(io.BytesIO(raw_bytes), AUDIO_DIR)
    return [
        {
            "japanese": n.japanese,
            "reading": n.reading,
            "english": n.english,
            "tags": deck_tag,
            "headword": n.headword,
            "audio_path": n.audio_path,
        }
        for n in notes
    ]


async def _do_import(new_rows: list[dict], skipped: int) -> ImportResult:
    if not new_rows:
        return ImportResult(imported=0, skipped_duplicates=skipped, embed_calls=0)

    with get_conn() as conn:
        new_ids = []
        for r in new_rows:
            cur = conn.execute(
                "INSERT INTO cards (japanese, reading, english, tags, headword, audio_path) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (r["japanese"], r["reading"], r["english"], r["tags"], r["headword"], r["audio_path"]),
            )
            new_ids.append(cur.lastrowid)
            conn.execute(
                "INSERT INTO reviews (card_id, due_date) VALUES (?, ?)",
                (cur.lastrowid, date.today().isoformat()),
            )

    embed_texts = [f"{r['japanese']} ||| {r['english']}" for r in new_rows]
    store = get_store()
    embed_calls = 0
    batches_this_window = 0
    window_start = time.monotonic()
    for start in range(0, len(embed_texts), EMBED_BATCH_SIZE):
        if not MOCK and batches_this_window >= MAX_BATCHES_PER_WINDOW:
            elapsed = time.monotonic() - window_start
            if elapsed < RATE_WINDOW_SECONDS:
                time.sleep(RATE_WINDOW_SECONDS - elapsed)
            window_start = time.monotonic()
            batches_this_window = 0

        batch = embed_texts[start : start + EMBED_BATCH_SIZE]
        batch_ids = new_ids[start : start + EMBED_BATCH_SIZE]
        vectors = embed(batch, input_type="search_document")
        for card_id, vec in zip(batch_ids, vectors):
            store.upsert(card_id, vec)
        embed_calls += 1
        batches_this_window += 1
    store.save()

    return ImportResult(imported=len(new_rows), skipped_duplicates=skipped, embed_calls=embed_calls)


@router.post("/import", response_model=ImportResult)
async def import_cards(file: UploadFile):
    raw = await file.read()
    filename = file.filename or ""

    if filename.lower().endswith(".apkg"):
        deck_tag = Path(filename).stem.lower().replace(" ", "-")
        parsed = _parse_apkg_rows(raw, deck_tag)
    else:
        parsed = _parse_csv_rows(raw.decode("utf-8"))

    with get_conn() as conn:
        existing = {
            (r["japanese"], r["english"])
            for r in conn.execute("SELECT japanese, english FROM cards").fetchall()
        }

    new_rows = [r for r in parsed if (r["japanese"], r["english"]) not in existing]
    skipped = len(parsed) - len(new_rows)

    return await _do_import(new_rows, skipped)
