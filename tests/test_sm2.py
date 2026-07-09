from datetime import date

from app.sm2 import ReviewState, grade


def test_first_three_good_reviews_follow_1_6_ease_progression():
    state = ReviewState()
    today = date(2026, 1, 1)

    state, due = grade(state, 5, today)
    assert state.repetitions == 1
    assert state.interval_days == 1
    assert due == date(2026, 1, 2)

    state, due = grade(state, 5, today)
    assert state.repetitions == 2
    assert state.interval_days == 6
    assert due == date(2026, 1, 7)

    state, due = grade(state, 5, today)
    assert state.repetitions == 3
    assert state.interval_days == round(6 * state.easiness)


def test_lapse_resets_repetitions_and_interval():
    state = ReviewState(easiness=2.5, interval_days=15, repetitions=4, lapses=0)
    today = date(2026, 1, 1)

    new_state, due = grade(state, 2, today)

    assert new_state.repetitions == 0
    assert new_state.interval_days == 1
    assert new_state.lapses == 1
    assert due == date(2026, 1, 2)


def test_easiness_floor_at_1_3():
    state = ReviewState(easiness=1.3, repetitions=3, interval_days=10)
    new_state, _ = grade(state, 0)
    assert new_state.easiness == 1.3


def test_quality_out_of_range_raises():
    import pytest

    with pytest.raises(ValueError):
        grade(ReviewState(), 6)
