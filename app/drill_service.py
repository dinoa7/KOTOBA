"""Adaptive drill generation: novel sentences constrained to known vocabulary."""

import json

from pydantic import ValidationError

from app import cohere_client
from app.db import get_conn
from app.models import Breakdown, DrillResponse

_SYSTEM_PROMPT = (
    "You are a Japanese sentence-writing engine for a vocabulary-constrained "
    "drill generator. Respond with ONLY a JSON array, no markdown fences, no "
    "commentary. Each array element must match this schema:\n"
    '{"japanese": "<sentence>", "hiragana": "<full hiragana rendering>", '
    '"english": "<natural translation>", "breakdown": [{"token": "...", '
    '"reading": "...", "dictionary_form": "...", "part_of_speech": "...", '
    '"meaning": "...", "grammar_note": "..."}], "grammar_points": ["..."]}\n'
    "Every token in each sentence must appear in its breakdown, in order."
)


def known_vocabulary() -> list[str]:
    """Words, not sentences: `japanese` is a full example sentence, so the
    constrained-generation prompt needs the standalone `headword` instead
    (falling back to the sentence for hand-added cards with no headword).
    """
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT c.headword, c.japanese FROM cards c JOIN reviews r ON r.card_id = c.id "
            "WHERE r.repetitions >= 2"
        ).fetchall()
    return [r["headword"] or r["japanese"] for r in rows]


def _build_prompt(grammar_point: str, count: int, vocab: list[str]) -> str:
    vocab_list = ", ".join(vocab) if vocab else "(no known vocabulary yet)"
    return (
        f"Generate {count} new Japanese sentences practicing {grammar_point}. "
        f"You may ONLY use words from this list: {vocab_list}. "
        "Respond in the JSON array breakdown format described in the system prompt."
    )


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
    return text.strip()


def _validate(raw: str) -> DrillResponse:
    cleaned = _strip_fences(raw)
    data = json.loads(cleaned)
    sentences = [Breakdown.model_validate(item) for item in data]
    return DrillResponse(sentences=sentences)


def generate_drill(grammar_point: str, count: int) -> DrillResponse:
    vocab = known_vocabulary()
    prompt = _build_prompt(grammar_point, count, vocab)
    raw = cohere_client.chat(_SYSTEM_PROMPT, prompt)
    try:
        return _validate(raw)
    except (json.JSONDecodeError, ValidationError) as e:
        retry_prompt = f"{prompt}\n\nYour previous response was invalid: {e}\nReturn ONLY the corrected JSON array."
        raw2 = cohere_client.chat(_SYSTEM_PROMPT, retry_prompt)
        return _validate(raw2)
