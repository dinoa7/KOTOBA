from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import AUDIO_DIR, BASE_DIR, IMAGES_DIR
from app.db import get_conn, init_db
from app.routers import breakdown, cards, confusions, drill, example, review, search

app = FastAPI(title="KOTOBA")

init_db()

app.include_router(cards.router)
app.include_router(review.router)
app.include_router(search.router)
app.include_router(breakdown.router)
app.include_router(example.router)
app.include_router(drill.router)
app.include_router(confusions.router)


@app.get("/api/stats")
def stats():
    with get_conn() as conn:
        total_calls = conn.execute("SELECT COUNT(*) AS n FROM api_log").fetchone()["n"]
        by_endpoint = conn.execute(
            """
            SELECT endpoint, COUNT(*) AS calls, AVG(latency_ms) AS avg_latency_ms
            FROM api_log GROUP BY endpoint
            """
        ).fetchall()
        card_count = conn.execute("SELECT COUNT(*) AS n FROM cards").fetchone()["n"]
    return {
        "total_calls": total_calls,
        "card_count": card_count,
        "by_endpoint": [dict(r) for r in by_endpoint],
    }


app.mount("/audio", StaticFiles(directory=AUDIO_DIR), name="audio")
app.mount("/images", StaticFiles(directory=IMAGES_DIR), name="images")

frontend_dir = BASE_DIR / "frontend"
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
