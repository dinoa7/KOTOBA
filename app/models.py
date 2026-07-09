from pydantic import BaseModel, Field


class CardIn(BaseModel):
    japanese: str
    reading: str | None = None
    english: str
    tags: str = ""
    headword: str = ""
    audio_path: str | None = None


class CardOut(CardIn):
    id: int
    created_at: str

    @classmethod
    def from_row(cls, row) -> "CardOut":
        return cls(
            id=row["id"],
            japanese=row["japanese"],
            reading=row["reading"],
            english=row["english"],
            tags=row["tags"],
            headword=row["headword"] or "",
            audio_path=row["audio_path"],
            created_at=row["created_at"],
        )


class ImportResult(BaseModel):
    imported: int
    skipped_duplicates: int
    embed_calls: int


class ReviewGrade(BaseModel):
    card_id: int
    quality: int = Field(ge=0, le=5)


class SearchResult(BaseModel):
    card: CardOut
    score: float


class Token(BaseModel):
    token: str
    reading: str
    dictionary_form: str = ""
    part_of_speech: str
    meaning: str
    grammar_note: str = ""


class Breakdown(BaseModel):
    japanese: str
    hiragana: str
    english: str
    breakdown: list[Token]
    grammar_points: list[str] = []


class BreakdownRequest(BaseModel):
    japanese: str
    card_id: int | None = None


class DrillRequest(BaseModel):
    grammar_point: str
    count: int = 3


class DrillResponse(BaseModel):
    sentences: list[Breakdown]


class ConfusionPair(BaseModel):
    card_a: CardOut
    card_b: CardOut
    similarity: float
    combined_lapses: int
