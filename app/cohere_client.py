"""Single wrapper around the Cohere SDK: timeout, 429 backoff with jitter,
latency logging to api_log, and a MOCK=1 mode that returns canned fixtures
so tests and offline dev never spend real API calls.
"""

import random
import time

import cohere
import httpx
from cohere import errors as cohere_errors

from app.config import CHAT_MODEL, COHERE_API_KEY, EMBED_MODEL, MOCK, RERANK_MODEL
from app.db import get_conn

REQUEST_TIMEOUT = 30
MAX_RETRIES = 4
BASE_BACKOFF = 1.0

# Transient failures worth retrying: rate limits, Cohere-side outages, and
# raw network blips. Anything else (bad request, auth, not found, ...) is a
# real error retrying won't fix, so it's left to propagate immediately.
RETRYABLE_ERRORS = (
    cohere_errors.TooManyRequestsError,
    cohere_errors.InternalServerError,
    cohere_errors.ServiceUnavailableError,
    cohere_errors.GatewayTimeoutError,
    cohere_errors.ClientClosedRequestError,
    httpx.TransportError,
    httpx.TimeoutException,
)

_client: cohere.ClientV2 | None = None


def _get_client() -> cohere.ClientV2:
    global _client
    if _client is None:
        _client = cohere.ClientV2(api_key=COHERE_API_KEY, timeout=REQUEST_TIMEOUT)
    return _client


def _log(endpoint: str, model: str, input_chars: int, latency_ms: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO api_log (endpoint, model, input_chars, latency_ms) VALUES (?, ?, ?, ?)",
            (endpoint, model, input_chars, latency_ms),
        )


def _with_retry(fn, endpoint: str, model: str, input_chars: int):
    last_err = None
    for attempt in range(MAX_RETRIES):
        start = time.monotonic()
        try:
            result = fn()
            latency_ms = int((time.monotonic() - start) * 1000)
            _log(endpoint, model, input_chars, latency_ms)
            return result
        except RETRYABLE_ERRORS as e:
            last_err = e
            sleep_s = BASE_BACKOFF * (2**attempt) + random.uniform(0, 0.5)
            time.sleep(sleep_s)
    raise last_err


def _mock_embedding(text: str) -> list[float]:
    """Deterministic, non-zero, word-overlap-sensitive stand-in for a real
    embedding, so MOCK=1 search/confusion tests exercise real cosine math
    instead of dividing by a zero vector.
    """
    import hashlib

    dims = 16
    vec = [0.0] * dims
    for word in text.lower().split():
        h = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16)
        vec[h % dims] += 1.0
    if not any(vec):
        vec[0] = 1.0
    return vec


def embed(texts: list[str], input_type: str) -> list[list[float]]:
    """Embed a batch of <=96 texts. Caller handles batching/rate limiting."""
    if MOCK:
        return [_mock_embedding(t) for t in texts]

    def call():
        resp = _get_client().embed(
            model=EMBED_MODEL,
            input_type=input_type,
            embedding_types=["float"],
            texts=texts,
        )
        return resp.embeddings.float_

    input_chars = sum(len(t) for t in texts)
    return _with_retry(call, "embed", EMBED_MODEL, input_chars)


def rerank(query: str, documents: list[str], top_n: int) -> list[dict]:
    """Returns list of {index, relevance_score} sorted by relevance."""
    if MOCK:
        return [{"index": i, "relevance_score": 1.0 - i * 0.01} for i in range(min(top_n, len(documents)))]

    def call():
        resp = _get_client().rerank(
            model=RERANK_MODEL,
            query=query,
            documents=documents,
            top_n=top_n,
        )
        return [{"index": r.index, "relevance_score": r.relevance_score} for r in resp.results]

    input_chars = len(query) + sum(len(d) for d in documents)
    return _with_retry(call, "rerank", RERANK_MODEL, input_chars)


def chat(system_prompt: str, user_message: str, temperature: float = 0.2) -> str:
    """Returns raw text content from a Command A chat call."""
    if MOCK:
        return _mock_chat_response(user_message)

    def call():
        resp = _get_client().chat(
            model=CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
        )
        return resp.message.content[0].text

    input_chars = len(system_prompt) + len(user_message)
    return _with_retry(call, "chat", CHAT_MODEL, input_chars)


_MOCK_SENTENCE = {
    "japanese": "これはテストです。",
    "hiragana": "これはてすとです。",
    "english": "This is a test.",
    "breakdown": [
        {
            "token": "これ",
            "reading": "これ",
            "dictionary_form": "これ",
            "part_of_speech": "pronoun",
            "meaning": "this",
            "grammar_note": "",
        },
        {
            "token": "は",
            "reading": "は",
            "dictionary_form": "は",
            "part_of_speech": "particle",
            "meaning": "topic marker",
            "grammar_note": "",
        },
        {
            "token": "テスト",
            "reading": "てすと",
            "dictionary_form": "テスト",
            "part_of_speech": "noun",
            "meaning": "test",
            "grammar_note": "",
        },
        {
            "token": "です",
            "reading": "です",
            "dictionary_form": "です",
            "part_of_speech": "copula",
            "meaning": "to be",
            "grammar_note": "polite",
        },
        {
            "token": "。",
            "reading": "。",
            "dictionary_form": "。",
            "part_of_speech": "punctuation",
            "meaning": "period",
            "grammar_note": "",
        },
    ],
    "grammar_points": ["copula です"],
}


def _mock_chat_response(user_message: str) -> str:
    """Canned fixture used when MOCK=1, so the full suite runs with zero API calls.

    Drill prompts ask for a JSON array of sentences; breakdown prompts ask for
    a single JSON object. Branch on the prompt shape so both callers validate.
    """
    import json

    if user_message.startswith("Generate "):
        return json.dumps([_MOCK_SENTENCE])
    return json.dumps(_MOCK_SENTENCE)
