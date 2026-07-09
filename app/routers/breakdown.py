from fastapi import APIRouter

from app.breakdown_service import get_breakdown
from app.models import Breakdown, BreakdownRequest

router = APIRouter(prefix="/breakdown", tags=["breakdown"])


@router.post("", response_model=Breakdown)
def breakdown(payload: BreakdownRequest):
    return get_breakdown(payload.japanese)
