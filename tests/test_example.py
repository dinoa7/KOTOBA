from fastapi.testclient import TestClient

from app.db import get_conn
from app.main import app

client = TestClient(app)


def test_example_returns_sentence_hiragana_and_english():
    resp = client.post("/example", json={"word": "これ"})
    assert resp.status_code == 200
    data = resp.json()
    assert set(data.keys()) == {"japanese", "hiragana", "english"}
    assert data["japanese"]
    assert data["hiragana"]
    assert data["english"]


def test_example_is_cached_by_word(monkeypatch):
    import app.example_service as example_service

    calls = {"n": 0}
    real_chat = example_service.cohere_client.chat

    def counting_chat(*args, **kwargs):
        calls["n"] += 1
        return real_chat(*args, **kwargs)

    monkeypatch.setattr(example_service.cohere_client, "chat", counting_chat)

    first = client.post("/example", json={"word": "これ"}).json()
    second = client.post("/example", json={"word": "これ"}).json()

    assert calls["n"] == 1  # second hit never left the cache
    assert first == second

    with get_conn() as conn:
        cached = conn.execute(
            "SELECT example_json FROM example_cache WHERE word = ?", ("これ",)
        ).fetchone()
    assert cached is not None


def test_different_words_get_their_own_cache_rows():
    client.post("/example", json={"word": "これ"})
    client.post("/example", json={"word": "です"})

    with get_conn() as conn:
        n = conn.execute("SELECT COUNT(*) AS n FROM example_cache").fetchone()["n"]
    assert n == 2
