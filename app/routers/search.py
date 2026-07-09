from fastapi import APIRouter

from app.cohere_client import embed, rerank
from app.db import get_conn
from app.models import CardOut, SearchResult
from app.vectors import get_store

router = APIRouter(prefix="/search", tags=["search"])

RECALL_K = 25
RERANK_TOP_N = 8


def _card_by_id(conn, card_id: int) -> CardOut:
    row = conn.execute("SELECT * FROM cards WHERE id = ?", (card_id,)).fetchone()
    return CardOut.from_row(row)


@router.get("", response_model=list[SearchResult])
def search(q: str):
    query_vec = embed([q], input_type="search_query")[0]
    store = get_store()
    candidates = store.top_k(query_vec, RECALL_K)
    if not candidates:
        return []

    with get_conn() as conn:
        cand_cards = {cid: _card_by_id(conn, cid) for cid, _ in candidates}

    documents = [
        f"{cand_cards[cid].japanese} ||| {cand_cards[cid].english}" for cid, _ in candidates
    ]
    ranked = rerank(q, documents, top_n=min(RERANK_TOP_N, len(documents)))

    results = []
    for r in ranked:
        card_id = candidates[r["index"]][0]
        results.append(SearchResult(card=cand_cards[card_id], score=r["relevance_score"]))
    return results
