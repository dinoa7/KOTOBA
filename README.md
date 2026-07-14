# KOTOBA (言葉)

A personal Japanese flashcard trainer that uses Cohere's Embed, Rerank, and
Command models to turn a flat deck of cards into a semantic, adaptive study
tool.

## The problem

Flashcard apps treat cards as isolated facts. They can't answer "show me
every card that uses the て-form," can't warn that 帰る and 変える keep
colliding in your head, and can't generate a fresh practice sentence using
only vocabulary you've already learned. A deck of N cards contains far more
structure than N facts — surfacing it takes a language model.

Every AI-generated output in KOTOBA follows one fixed study format: original
Japanese → full hiragana reading → a word-by-word breakdown table with
grammar notes.

## Features

- **Review** — SM-2 spaced repetition, entirely offline, laid out the way
  Anki decks render: the card front shows the sentence with its target word
  colored (using the deck's own highlight markup), and the back reveals the
  word's own reading and definition first, then the sentence furigana and
  translation. The note's picture (when the deck includes one) appears above
  the word definition. A "Breakdown" button on any card hits the (usually
  cached) breakdown endpoint, and every token row in the breakdown has an
  "Example" button that generates one fresh example sentence for that word —
  the plain sentence (target word in red), its full-hiragana rendering
  (target word in black), and an English translation. Examples are cached
  per dictionary-form word so repeat requests are free, and toggle closed
  with the same button once generated.
- **Search** — semantic, not keyword: embed the query, rank locally by
  cosine similarity, rerank the top candidates. Works in Japanese or
  English, and understands typed romaji ("te" → て) without corrupting real
  English queries.
- **Drill** — generates fresh practice sentences constrained to vocabulary
  you've already reviewed at least twice, targeting a grammar point you
  choose — no word outside your own known-vocab list is ever used.
- **Confusions** — pure local math, zero API calls: pairwise cosine
  similarity across every card, cross-referenced with lapse counts, surfaces
  pairs you keep mixing up so they can be drilled side by side.
- **Recent** — a chronological log of every card you've graded, most recent
  first. Paired with a one-step "Back" button on the Review tab that undoes
  the last grade — restoring the prior SM-2 state on the server, not just
  the on-screen card.
- **Import** — raw Anki `.apkg`, sentence + audio extracted directly.

## Why Cohere

| Need | Model | Endpoint |
|---|---|---|
| Sentence breakdowns, drill generation, per-token examples | `command-a-03-2025` | `/breakdown`, `/drill`, `/example` |
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

Raw Anki `.apkg`, via the Import tab or `POST /cards/import` — uploaded
directly, no conversion step. KOTOBA parses the note's `Sentence`/`Sentence
Meaning` fields as the card's `japanese`/`english` (not the bare vocab word —
see "Sentence-first, not word-first" below), keeps the vocab word separately
as `headword` along with its `Word Reading`/`Word Meaning` fields and the
deck's own bold markup marking the target word inside the sentence, and
extracts the sentence's audio clip into `data/audio/` and the note's
Picture into `data/images/` for in-app playback and display.
Duplicates are keyed on (sentence, meaning, headword) — sentence-per-word
decks legitimately reuse one sentence for several target words. Re-importing
a deck backfills word fields onto existing cards without new embed calls or
touching SRS state.

```bash
curl -F "file=@my_deck.apkg" http://127.0.0.1:8000/cards/import
```

### Run tests (zero API calls)

```bash
pytest
```

`tests/conftest.py` sets `MOCK=1` and points storage at a temp directory, so
the full suite runs offline against canned Cohere fixtures
([app/cohere_client.py](app/cohere_client.py)).

## Budget

Trial tier: 1,000 Cohere calls/month. Daily use (imports once, ~5
breakdowns/day, ~3 drills/day, ~2 searches/day) lands around 366 calls/month.
`GET /api/stats` reports real logged latency and call counts from the
`api_log` table.

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
- **Two clocks for repetition, not one.** SM-2's `due_date` (days) still
  governs when a card comes back on a *future day*. Layered on top,
  grading also re-inserts the card into the *current session's* queue at a
  distance that compounds with SM-2's own `repetitions` count (which resets
  to 0 the moment a card is graded Hard or Very Hard) — so a card
  consistently graded Very Easy gets pushed farther out each time, fast
  enough to fall out of a normal-sized session entirely, while a
  struggling card always snaps back to a short, flat distance regardless
  of history. Session-local only (an in-memory JS array, not persisted) —
  restarting the page resets it, same as Anki's learning queue
  ([frontend/app.js](frontend/app.js)).
- **Undo by snapshot, not by inverse math.** SM-2 grading isn't cleanly
  invertible — `repetitions`/`lapses` resets aren't reversible arithmetic —
  so the one-step "Back" button doesn't try to compute its way back.
  `POST /review/grade` writes the *pre-grade* row to a `review_log` table
  before overwriting `reviews`; `POST /review/undo` just restores that
  snapshot and deletes the log row. The same table doubles as the Recent
  tab's activity feed ([app/routers/review.py](app/routers/review.py)).
- **One reveal pattern, everywhere.** Search, Confusions, Recent, and Drill
  all gate a card's reading/translation behind the same accent-colored
  "Show Answer" control used on the Review tab, and it toggles back to
  "Minimize" rather than committing to a one-way reveal — so browsing
  results doesn't force every card open at once
  ([frontend/app.js](frontend/app.js): `renderRevealBlock`).
- **Anki `.apkg` only, no CSV.** An early CSV importer was dropped —
  `.apkg` already carries structured fields and audio in one file, so
  maintaining a second hand-rolled parser for a strictly worse format
  wasn't worth it ([app/routers/cards.py](app/routers/cards.py)).
- **The deck's own markup is the highlight source, not substring matching.**
  Anki renders note fields as raw HTML, so sentence-per-word decks mark the
  target word by bolding it inside the Sentence field
  (`あの<b>人</b>はいい人です。`). That markup is the only reliable signal for
  *which occurrence* is the target — 人 appears twice in that sentence, and
  the deck also bolds conjugated surface forms (聞いて) that dictionary-form
  headword matching (聞く) would miss. Import preserves it in a `highlight`
  column; plain-text `japanese` stays the source for embeddings, prompts,
  and dedup ([app/anki_import.py](app/anki_import.py)). Headword substring
  matching survives only as a display fallback for cards without markup.

## Video demo
https://youtu.be/C85SlkMwqmY
