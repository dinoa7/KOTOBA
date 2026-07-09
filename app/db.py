import sqlite3
from contextlib import contextmanager

from app.config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS cards (
    id INTEGER PRIMARY KEY,
    japanese TEXT NOT NULL,        -- the example sentence, not a bare word
    reading TEXT,
    english TEXT NOT NULL,
    tags TEXT DEFAULT '',
    headword TEXT DEFAULT '',      -- the single vocab word this sentence drills; feeds drill's known-vocab list
    audio_path TEXT,               -- filename under data/audio/, served at /audio/<audio_path>
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS reviews (
    card_id INTEGER PRIMARY KEY REFERENCES cards(id),
    easiness REAL DEFAULT 2.5,
    interval_days INTEGER DEFAULT 0,
    repetitions INTEGER DEFAULT 0,
    due_date TEXT,
    lapses INTEGER DEFAULT 0,
    total_reviews INTEGER DEFAULT 0  -- monotonic count of every grade ever given, pass or fail
);

CREATE TABLE IF NOT EXISTS breakdown_cache (
    sentence_hash TEXT PRIMARY KEY,
    breakdown_json TEXT NOT NULL,
    model TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS api_log (
    id INTEGER PRIMARY KEY,
    endpoint TEXT,
    model TEXT,
    input_chars INTEGER,
    latency_ms INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """Add columns introduced after initial release to any pre-existing db."""
    existing_cards = {row["name"] for row in conn.execute("PRAGMA table_info(cards)")}
    if "headword" not in existing_cards:
        conn.execute("ALTER TABLE cards ADD COLUMN headword TEXT DEFAULT ''")
    if "audio_path" not in existing_cards:
        conn.execute("ALTER TABLE cards ADD COLUMN audio_path TEXT")

    existing_reviews = {row["name"] for row in conn.execute("PRAGMA table_info(reviews)")}
    if "total_reviews" not in existing_reviews:
        conn.execute("ALTER TABLE reviews ADD COLUMN total_reviews INTEGER DEFAULT 0")


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(SCHEMA)
        _migrate(conn)


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()
