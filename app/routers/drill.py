from fastapi import APIRouter

from app.drill_service import generate_drill
from app.models import DrillRequest, DrillResponse

router = APIRouter(prefix="/drill", tags=["drill"])


@router.post("", response_model=DrillResponse)
def drill(payload: DrillRequest):
    return generate_drill(payload.grammar_point, payload.count)
