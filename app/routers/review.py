from datetime import date

from fastapi import APIRouter, HTTPException

from app.db import get_conn
from app.models import CardOut, RecentReview, ReviewGrade
from app.sm2 import ReviewState, grade

router = APIRouter(prefix="/review", tags=["review"])


@router.get("/due", response_model=list[CardOut])
def due_cards():
    today = date.today().isoformat()
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT c.*, r.total_reviews AS review_count FROM cards c
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
        total_reviews = row["total_reviews"] + 1

        conn.execute(
            """
            INSERT INTO review_log (card_id, quality, prev_easiness, prev_interval_days,
                prev_repetitions, prev_due_date, prev_lapses, prev_total_reviews)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                payload.card_id,
                payload.quality,
                row["easiness"],
                row["interval_days"],
                row["repetitions"],
                row["due_date"],
                row["lapses"],
                row["total_reviews"],
            ),
        )

        conn.execute(
            """
            UPDATE reviews SET easiness = ?, interval_days = ?, repetitions = ?,
                due_date = ?, lapses = ?, total_reviews = ? WHERE card_id = ?
            """,
            (
                new_state.easiness,
                new_state.interval_days,
                new_state.repetitions,
                due_date.isoformat(),
                new_state.lapses,
                total_reviews,
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
        "review_count": total_reviews,
    }


@router.get("/recent", response_model=list[RecentReview])
def recent_reviews(limit: int = 20):
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT c.*, r.total_reviews AS review_count,
                rl.quality AS log_quality, rl.graded_at AS log_graded_at
            FROM review_log rl
            JOIN cards c ON c.id = rl.card_id
            JOIN reviews r ON r.card_id = c.id
            ORDER BY rl.id DESC LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        RecentReview(card=CardOut.from_row(r), quality=r["log_quality"], graded_at=r["log_graded_at"])
        for r in rows
    ]


@router.post("/undo")
def undo_last_grade():
    with get_conn() as conn:
        log_row = conn.execute(
            "SELECT * FROM review_log ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if log_row is None:
            raise HTTPException(status_code=404, detail="nothing to undo")

        conn.execute(
            """
            UPDATE reviews SET easiness = ?, interval_days = ?, repetitions = ?,
                due_date = ?, lapses = ?, total_reviews = ? WHERE card_id = ?
            """,
            (
                log_row["prev_easiness"],
                log_row["prev_interval_days"],
                log_row["prev_repetitions"],
                log_row["prev_due_date"],
                log_row["prev_lapses"],
                log_row["prev_total_reviews"],
                log_row["card_id"],
            ),
        )
        conn.execute("DELETE FROM review_log WHERE id = ?", (log_row["id"],))

    return {"card_id": log_row["card_id"], "review_count": log_row["prev_total_reviews"]}
