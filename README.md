# KOTOBA (言葉)

A personal Japanese flashcard trainer that uses Cohere's Embed, Rerank, and
Command models to turn a flat deck of cards into a semantic, adaptive study
tool. See [KOTOBA_Build_Spec.md](KOTOBA_Build_Spec.md) for the full design
rationale.

## Why Cohere

| Need | Model | Endpoint |
|---|---|---|
| Sentence breakdowns, drill generation | `command-a-03-2025` | `/breakdown`, `/drill` |
| Semantic card search, confusion detection | `embed-v4.0` | embedded once at import |
| "Which cards answer this question?" | `rerank-v4.0-pro` | `/search` |

Embed → Rerank → Command: recall, precision, generation.

## Architecture

```
Browser (vanilla JS)  →  FastAPI (Python 3.11+)  →  SQLite + numpy .npz vectors
                                                   →  Cohere Python SDK (ClientV2)
```

- **Embed once, cache forever.** Cards are embedded at import; breakdowns are
  cached in SQLite by sentence hash.
- **SRS is local.** SM-2 scheduling ([app/sm2.py](app/sm2.py)) is pure
  arithmetic — no API call is ever spent on it.
- **Graceful degradation.** Review mode works fully offline; AI features show
  a clear "offline" state if the API is unreachable.
- **Secrets hygiene.** `COHERE_API_KEY` lives in `.env` (gitignored).

## Setup

```bash
py -m venv .venv
./.venv/Scripts/activate       # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
cp .env.example .env           # then paste in your Cohere trial API key
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 — the FastAPI app serves the frontend directly
(no separate frontend build step).

### Import a starter deck

Two supported formats, both via the Import tab or `POST /cards/import`:

- **Raw Anki `.apkg`** (recommended) — uploaded directly, no conversion step.
  KOTOBA parses the note's `Sentence`/`Sentence Meaning` fields as the card's
  `japanese`/`english` (not the bare vocab word — see "Sentence-first, not
  word-first" below), keeps the vocab word separately as `headword`, and
  extracts the sentence's audio clip into `data/audio/` for in-app playback.
  ```bash
  curl -F "file=@my_deck.apkg" http://127.0.0.1:8000/cards/import
  ```
- **CSV**: `japanese,reading,english,tags[,headword,audio_path]` — the last
  two columns are optional.
  ```bash
  curl -F "file=@my_deck.csv" http://127.0.0.1:8000/cards/import
  ```

### Run tests (zero API calls)

```bash
pytest
```

`tests/conftest.py` sets `MOCK=1` and points storage at a temp directory, so
the full suite runs offline against canned Cohere fixtures
([app/cohere_client.py](app/cohere_client.py)).

## Budget

Trial tier: 1,000 Cohere calls/month. See §6 of the build spec for the math —
daily use (imports once, ~5 breakdowns/day, ~3 drills/day, ~2 searches/day)
lands around 366 calls/month. `GET /api/stats` reports real logged latency
and call counts from the `api_log` table.

## Design decisions

- **Brute-force cosine similarity in numpy**, not a vector database — at
  hundreds to low thousands of cards this is instant, and a vector DB here
  would be resume-driven overengineering.
- **Cache-first breakdowns**, keyed by SHA-256 of the sentence — re-viewing a
  card's breakdown never costs another API call.
- **Strict JSON contracts** for every generative endpoint, validated with
  Pydantic, with one retry (error message appended to the prompt) before
  failing gracefully.
- **temperature=0.2** on Command A calls — grammar breakdowns should be
  consistent, not creative.
- **Sentence-first, not word-first.** A card's `japanese` field is a full
  example sentence (with audio), not a bare vocabulary word — the point of
  the app is breaking down and drilling real sentence structure, not
  flashing single words. The standalone word still matters for one thing:
  constraining drill generation to vocabulary you actually know, so it's
  kept in a separate `headword` column and only used there
  ([app/drill_service.py](app/drill_service.py)).
- **Romaji-aware search, without corrupting English queries.** Search
  understands typed romaji ("te" finds て) by appending a kana conversion to
  the query before embedding — but only for words that round-trip cleanly
  through romaji-to-kana-and-back, so real English words ("good", "counting
  people") aren't mangled into nonsense kana and appended as noise
  ([app/romaji.py](app/romaji.py)).

---

*Setup steps that happen outside the editor — installing Python, getting a
Cohere API key, running the server, etc. — are documented in the "Outside
VS Code" section of [KOTOBA_Build_Spec.md](KOTOBA_Build_Spec.md#appendix-outside-vs-code-what-to-do-outside-the-editor).*
