from datetime import date

from fastapi import APIRouter, HTTPException

from app.db import get_conn
from app.models import CardOut, ReviewGrade
from app.sm2 import ReviewState, grade

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/due", response_model=list[CardOut])
def due_cards():
    today = date.today().isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT c.* FROM cards c
            JOIN reviews r ON r.card_id = c.id
            WHERE r.due_date <= ?
            ORDER BY r.due_date
            """,
            (today,),
        ).fetchall()
    return [CardOut.from_row(r) for r in rows]


@router.post("/grade")
def grade_card(payload: ReviewGrade):
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM reviews WHERE card_id = ?", (payload.card_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="no review state for card")

        state = ReviewState(
            easiness=row["easiness"],
            interval_days=row["interval_days"],
            repetitions=row["repetitions"],
            lapses=row["lapses"],
        )
        new_state, due_date = grade(state, payload.quality)

        conn.execute(
            """
            UPDATE reviews SET easiness = ?, interval_days = ?, repetitions = ?,
                due_date = ?, lapses = ? WHERE card_id = ?
            """,
            (
                new_state.easiness,
                new_state.interval_days,
                new_state.repetitions,
                due_date.isoformat(),
                new_state.lapses,
                payload.card_id,
            ),
        )

    return {
        "card_id": payload.card_id,
        "easiness": new_state.easiness,
        "interval_days": new_state.interval_days,
        "repetitions": new_state.repetitions,
        "due_date": due_date.isoformat(),
        "lapses": new_state.lapses,
    }
