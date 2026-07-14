from pydantic import BaseModel, Field


class CardIn(BaseModel):
    japanese: str
    reading: str | None = None
    english: str
    tags: str = ""
    headword: str = ""
    word_reading: str = ""
    word_meaning: str = ""
    highlight: str | None = None
    audio_path: str | None = None
    image_path: str | None = None


class CardOut(CardIn):
    id: int
    created_at: str
    review_count: int = 0

    @classmethod
    def from_row(cls, row) -> "CardOut":
        row_keys = row.keys()
        return cls(
            id=row["id"],
            japanese=row["japanese"],
            reading=row["reading"],
            english=row["english"],
            tags=row["tags"],
            headword=row["headword"] or "",
            word_reading=(row["word_reading"] if "word_reading" in row_keys else "") or "",
            word_meaning=(row["word_meaning"] if "word_meaning" in row_keys else "") or "",
            highlight=row["highlight"] if "highlight" in row_keys else None,
            audio_path=row["audio_path"],
            image_path=row["image_path"] if "image_path" in row_keys else None,
            created_at=row["created_at"],
            review_count=row["review_count"] if "review_count" in row_keys else 0,
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


class RecentReview(BaseModel):
    card: CardOut
    quality: int
    graded_at: str


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


class ExampleRequest(BaseModel):
    word: str


class ExampleSentence(BaseModel):
    japanese: str
    hiragana: str
    english: str


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
