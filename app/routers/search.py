from fastapi import APIRouter

from app.cohere_client import embed, rerank
from app.db import get_conn
from app.models import CardOut, SearchResult
from app.romaji import romaji_hint
from app.vectors import get_store

router = APIRouter(prefix="/search", tags=["search"])

RECALL_K = 25
RERANK_TOP_N = 8


def _card_by_id(conn, card_id: int) -> CardOut:
    row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
    return CardOut.from_row(row)


@router.get("", response_model=list[SearchResult])
def search(q: str):
    # Someone without a Japanese IME can type "te" and have it understood
    # as て. Appended, not substituted, so a query that's genuinely English
    # ("good", "counting people") is untouched — romaji_hint() only returns
    # kana for words that round-trip cleanly as romaji in the first place.
    hint = romaji_hint(q)
    expanded_q = f"{q} {hint}" if hint else q

    query_vec = embed([expanded_q], input_type="search_query")[0]
    store = get_store()
    candidates = store.top_k(query_vec, RECALL_K)
    if not candidates:
        return []

    with get_conn() as conn:
        cand_cards = {cid: _card_by_id(conn, cid) for cid, _ in candidates}

    documents = [
        f"{cand_cards[cid].japanese} ||| {cand_cards[cid].english}" for cid, _ in candidates
    ]
    # Rank *all* recalled candidates (free — top_n only limits what's returned,
    # not the cost) so we can dedupe by sentence text below and still end up
    # with RERANK_TOP_N distinct results. Anki decks commonly reuse one
    # example sentence across several vocab notes (different headword, same
    # text), which would otherwise show the same sentence twice in a row.
    ranked = rerank(expanded_q, documents, top_n=len(documents))

    results = []
    seen_sentences = set()
    for r in ranked:
        card_id = candidates[r["index"]][0]
        card = cand_cards[card_id]
        if card.japanese in seen_sentences:
            continue
        seen_sentences.add(card.japanese)
        results.append(SearchResult(card=card, score=r["relevance_score"]))
        if len(results) >= RERANK_TOP_N:
            break
    return results
