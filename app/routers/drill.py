from fastapi import APIRouter, HTTPException

from app.drill_service import NoKnownVocabularyError, generate_drill
from app.models import DrillRequest, DrillResponse

router = APIRouter(prefix="/drill", tags=["drill"])


@router.post("", response_model=DrillResponse)
def drill(payload: DrillRequest):
    try:
        return generate_drill(payload.grammar_point, payload.count)
    except NoKnownVocabularyError as e:
        raise HTTPException(status_code=400, detail=str(e))
