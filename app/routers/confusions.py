"""Pure local math, zero API calls: pairwise cosine similarity across all
card vectors, cross-referenced with review lapses, to surface cards that are
semantically close and frequently missed.
"""

from fastapi import APIRouter

from app.db import get_conn
from app.models import CardOut, ConfusionPair
from app.vectors import get_store

router = APIRouter(prefix="/confusions", tags=["confusions"])

TOP_N_PAIRS = 15


def _card_and_lapses(conn, card_id: int) -> tuple[CardOut, int]:
    row = conn.execute(
        """
        SELECT c.*, COALESCE(r.lapses, 0) AS lapses FROM cards c
        LEFT JOIN reviews r ON r.card_id = c.id
        WHERE c.id = ?
        """,
        (card_id,),
    ).fetchone()
    return CardOut.from_row(row), row["lapses"]


@router.get("", response_model=list[ConfusionPair])
def confusions():
    store = get_store()
    pairs = store.all_pairs_top(TOP_N_PAIRS)

    with get_conn() as conn:
        results = []
        for id_a, id_b, sim in pairs:
            card_a, lapses_a = _card_and_lapses(conn, id_a)
            card_b, lapses_b = _card_and_lapses(conn, id_b)
            results.append(
                ConfusionPair(
                    card_a=card_a, card_b=card_b, similarity=sim,
                    combined_lapses=lapses_a + lapses_b,
                )
            )

    results.sort(key=lambda p: (-p.combined_lapses, -p.similarity))
    return results
