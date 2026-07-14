"""Per-word example sentences for breakdown tokens: strict JSON contract,
Pydantic validation, retry-once-on-invalid, and word-keyed caching in SQLite
— same shape as breakdown_service, but keyed by dictionary-form word so every
card that shares a token shares one cached example.
"""

import json

from pydantic import ValidationError

from app import cohere_client
from app.breakdown_service import _strip_fences
from app.config import CHAT_MODEL, PROMPTS_DIR
from app.db import get_conn
from app.models import ExampleSentence

_SYSTEM_PROMPT = (PROMPTS_DIR / "example.txt").read_text(encoding="utf-8")


def get_cached(word: str) -> ExampleSentence | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT example_json FROM example_cache WHERE word = ?", (word,)
        ).fetchone()
    if row is None:
        return None
    return ExampleSentence.model_validate_json(row["example_json"])


def _store_cache(word: str, example: ExampleSentence) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO example_cache (word, example_json, model) VALUES (?, ?, ?)",
            (word, example.model_dump_json(), CHAT_MODEL),
        )


def get_example(word: str) -> ExampleSentence:
    cached = get_cached(word)
    if cached is not None:
        return cached

    raw = cohere_client.chat(_SYSTEM_PROMPT, word)
    example = _parse_and_validate(raw, word)
    _store_cache(word, example)
    return example


def _parse_and_validate(raw: str, word: str) -> ExampleSentence:
    try:
        return _validate(raw)
    except (json.JSONDecodeError, ValidationError) as e:
        retry_prompt = (
            f"{word}\n\nYour previous response was invalid: {e}\n"
            "Return ONLY the corrected JSON object."
        )
        raw2 = cohere_client.chat(_SYSTEM_PROMPT, retry_prompt)
        return _validate(raw2)


def _validate(raw: str) -> ExampleSentence:
    cleaned = _strip_fences(raw)
    data = json.loads(cleaned)
    return ExampleSentence.model_validate(data)
