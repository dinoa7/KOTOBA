"""Shared breakdown logic: strict JSON contract, Pydantic validation,
retry-once-on-invalid, and sentence-hash caching in SQLite.
"""

import hashlib
import json

from pydantic import ValidationError

from app import cohere_client
from app.config import CHAT_MODEL, PROMPTS_DIR
from app.db import get_conn
from app.models import Breakdown

_SYSTEM_PROMPT = (PROMPTS_DIR / "breakdown.txt").read_text(encoding="utf-8")


def _sentence_hash(japanese: str) -> str:
    return hashlib.sha256(japanese.encode("utf-8")).hexdigest()


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


def get_cached(japanese: str) -> Breakdown | None:
    h = _sentence_hash(japanese)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT breakdown_json FROM breakdown_cache WHERE sentence_hash = ?", (h,)
        ).fetchone()
    if row is None:
        return None
    return Breakdown.model_validate_json(row["breakdown_json"])


def _store_cache(japanese: str, breakdown: Breakdown) -> None:
    h = _sentence_hash(japanese)
    with get_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO breakdown_cache (sentence_hash, breakdown_json, model) "
            "VALUES (?, ?, ?)",
            (h, breakdown.model_dump_json(), CHAT_MODEL),
        )


def get_breakdown(japanese: str) -> Breakdown:
    cached = get_cached(japanese)
    if cached is not None:
        return cached

    raw = cohere_client.chat(_SYSTEM_PROMPT, japanese)
    breakdown = _parse_and_validate(raw, japanese)
    _store_cache(japanese, breakdown)
    return breakdown


def _parse_and_validate(raw: str, japanese: str) -> Breakdown:
    try:
        return _validate(raw)
    except (json.JSONDecodeError, ValidationError) as e:
        retry_prompt = (
            f"{japanese}\n\nYour previous response was invalid: {e}\n"
            "Return ONLY the corrected JSON object."
        )
        raw2 = cohere_client.chat(_SYSTEM_PROMPT, retry_prompt)
        return _validate(raw2)


def _validate(raw: str) -> Breakdown:
    cleaned = _strip_fences(raw)
    data = json.loads(cleaned)
    return Breakdown.model_validate(data)
