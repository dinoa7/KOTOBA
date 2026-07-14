from fastapi import APIRouter

from app.example_service import get_example
from app.models import ExampleRequest, ExampleSentence

router = APIRouter(prefix="/example", tags=["example"])


@router.post("", response_model=ExampleSentence)
def example(payload: ExampleRequest):
    return get_example(payload.word)
