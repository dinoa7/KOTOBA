"""SM-2 spaced-repetition scheduling. Pure arithmetic, no I/O."""

from dataclasses import dataclass
from datetime import date, timedelta


@dataclass
class ReviewState:
    easiness: float = 2.5
    interval_days: int = 0
    repetitions: int = 0
    lapses: int = 0


def grade(state: ReviewState, quality: int, today: date | None = None) -> tuple[ReviewState, date]:
    """Apply an SM-2 grade (0-5) to a review state, returning the next state.

    quality < 3 is a lapse: repetitions reset and the card is due again tomorrow.
    quality >= 3 advances the repetition count and grows the interval.
    """
    if not 0 <= quality <= 5:
        raise ValueError("quality must be between 0 and 5")

    today = today or date.today()

    easiness = state.easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    easiness = max(1.3, easiness)

    if quality < 3:
        repetitions = 0
        interval_days = 1
        lapses = state.lapses + 1
    else:
        repetitions = state.repetitions + 1
        lapses = state.lapses
        if repetitions == 1:
            interval_days = 1
        elif repetitions == 2:
            interval_days = 6
        else:
            interval_days = round(state.interval_days * easiness)

    due_date = today + timedelta(days=interval_days)

    return ReviewState(
        easiness=easiness,
        interval_days=interval_days,
        repetitions=repetitions,
        lapses=lapses,
    ), due_date
