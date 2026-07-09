"""Romaji-aware search: lets someone without a Japanese IME type "te" and
have it understood as て, without corrupting genuine English queries.

jaconv's alphabet2kana is a best-effort forced mapping — fed an English word
like "good" or "requests" it still produces *something* (ごおっ, れくえっっっ),
just nonsense. So a word is only trusted as romaji if converting it to kana
and back reproduces the original word; real romaji round-trips cleanly,
English mostly doesn't.
"""

import re

import jaconv

_WORD_RE = re.compile(r"[A-Za-z]+")


def _is_confident_romaji(word: str) -> str | None:
    kana = jaconv.alphabet2kana(word.lower())
    if not kana:
        return None
    roundtrip = jaconv.kana2alphabet(kana)
    if roundtrip.lower() == word.lower():
        return kana
    return None


def romaji_hint(query: str) -> str | None:
    """Returns a space-joined string of the kana conversions for every
    ASCII word in `query` that round-trips cleanly as romaji, or None if
    no word qualified. Non-ASCII words (existing kana/kanji, punctuation,
    numbers) are left alone entirely.
    """
    converted = []
    for word in _WORD_RE.findall(query):
        kana = _is_confident_romaji(word)
        if kana:
            converted.append(kana)
    return " ".join(converted) if converted else None
