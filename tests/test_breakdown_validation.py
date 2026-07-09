import pytest

from app import breakdown_service
from app.models import Breakdown


def test_mock_breakdown_validates_and_caches():
    result = breakdown_service.get_breakdown("これはテストです。")

    assert isinstance(result, Breakdown)
    assert result.breakdown[0].token == "これ"

    cached = breakdown_service.get_cached("これはテストです。")
    assert cached is not None
    assert cached.japanese == result.japanese


def test_invalid_json_retries_once_then_succeeds(monkeypatch):
    responses = iter(["not json at all", '{"japanese": "x", "hiragana": "x", "english": "x", "breakdown": [], "grammar_points": []}'])
    monkeypatch.setattr(breakdown_service.cohere_client, "chat", lambda *a, **k: next(responses))

    result = breakdown_service.get_breakdown("some unseen sentence")

    assert result.japanese == "x"


def test_invalid_json_twice_raises(monkeypatch):
    monkeypatch.setattr(breakdown_service.cohere_client, "chat", lambda *a, **k: "still not json")

    with pytest.raises(Exception):
        breakdown_service.get_breakdown("another unseen sentence")


def test_fenced_json_is_stripped_before_parsing():
    fenced = '```json\n{"japanese": "y", "hiragana": "y", "english": "y", "breakdown": [], "grammar_points": []}\n```'
    result = breakdown_service._validate(fenced)
    assert result.japanese == "y"
