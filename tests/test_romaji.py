from app.romaji import romaji_hint


def test_single_romaji_word_converts_to_kana():
    assert romaji_hint("te") == "て"


def test_full_romaji_phrase_converts_word_by_word():
    assert romaji_hint("watashi wa gakusei desu") == "わたし わ がくせい です"


def test_english_word_is_not_mistaken_for_romaji():
    assert romaji_hint("good") is None
    assert romaji_hint("person") is None


def test_mixed_query_only_converts_the_romaji_words():
    # Matches the spec's own example query. "form" and "requests" don't
    # round-trip as romaji, so they should be left out of the hint.
    hint = romaji_hint("te form requests")
    assert hint == "て"


def test_existing_kana_query_produces_no_hint():
    assert romaji_hint("かえる") is None


def test_empty_query_produces_no_hint():
    assert romaji_hint("") is None
