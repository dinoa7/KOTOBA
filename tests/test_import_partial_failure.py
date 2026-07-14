import asyncio

import pytest
from fastapi import HTTPException

import app.routers.cards as cards_module
from app.db import get_conn

EMBED_BATCH_SIZE = cards_module.EMBED_BATCH_SIZE


def _rows(n, prefix="row"):
    return [
        {
            "japanese": f"{prefix}{i}",
            "reading": "",
            "english": f"english{i}",
            "tags": "",
            "headword": "",
            "word_reading": "",
            "word_meaning": "",
            "highlight": None,
            "audio_path": None,
            "image_path": None,
        }
        for i in range(n)
    ]


def _flaky_embed(real_embed, fail_on_call):
    calls = {"n": 0}

    def flaky(texts, input_type):
        calls["n"] += 1
        if calls["n"] == fail_on_call:
            raise RuntimeError("simulated Cohere outage")
        return real_embed(texts, input_type)

    return flaky


def test_failure_partway_through_leaves_earlier_batches_committed_and_embedded(monkeypatch):
    # Two full batches' worth of rows, so the failure hits the second batch.
    rows = _rows(EMBED_BATCH_SIZE + 5)
    monkeypatch.setattr(cards_module, "embed", _flaky_embed(cards_module.embed, fail_on_call=2))

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(cards_module._do_import(rows, skipped=0))

    assert exc_info.value.status_code == 502
    assert f"{EMBED_BATCH_SIZE} of {len(rows)}" in exc_info.value.detail

    with get_conn() as conn:
        stored = {r["japanese"] for r in conn.execute("SELECT japanese FROM cards").fetchall()}
    assert len(stored) == EMBED_BATCH_SIZE
    assert "row0" in stored
    assert f"row{EMBED_BATCH_SIZE}" not in stored  # first row of the failed batch never got inserted


def test_rerunning_import_after_failure_only_imports_the_missing_rows(monkeypatch):
    rows = _rows(EMBED_BATCH_SIZE + 5)
    monkeypatch.setattr(cards_module, "embed", _flaky_embed(cards_module.embed, fail_on_call=2))

    with pytest.raises(HTTPException):
        asyncio.run(cards_module._do_import(rows, skipped=0))

    # Second attempt: caller is responsible for re-filtering dupes against
    # the DB (as the /cards/import endpoint does), so only the un-imported
    # tail is passed back in.
    monkeypatch.undo()
    with get_conn() as conn:
        already_imported = {r["japanese"] for r in conn.execute("SELECT japanese FROM cards").fetchall()}
    remaining_rows = [r for r in rows if r["japanese"] not in already_imported]

    result = asyncio.run(cards_module._do_import(remaining_rows, skipped=len(rows) - len(remaining_rows)))

    assert result.imported == len(remaining_rows)
    with get_conn() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM cards").fetchone()["n"]
    assert total == len(rows)
