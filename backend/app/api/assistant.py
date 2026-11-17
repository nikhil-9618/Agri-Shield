"""Voice assistant endpoint (speech-to-text happens on the phone)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from ..db import User
from ..schemas import AssistantIn, AssistantOut
from ..security import get_current_user
from ..services.advisory import get_advisory_service
from ..services.assistant import AssistantService
from ..services.weather import WeatherService

router = APIRouter(prefix="/api/assistant", tags=["assistant"])

_advisory = get_advisory_service()
_service = AssistantService(_advisory, WeatherService(_advisory))


@router.post("/ask", response_model=AssistantOut)
async def ask(
    payload: AssistantIn,
    user: User = Depends(get_current_user),
) -> AssistantOut:
    question = " ".join(payload.question.split())
    if len(question) < 2:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "empty_question", "message": "Please ask a question."},
        )
    result = await _service.ask(
        question,
        payload.language or user.language,
        payload.latitude,
        payload.longitude,
    )
    return AssistantOut(**result)
