"""Groundedness Check API."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.chroma_client import ChromaClient
from app.core.settings import Settings, get_settings
from app.services.groundedness import (
    GroundednessChecker,
    GroundednessCheckRequest as ServiceGroundednessRequest,
)

router = APIRouter()


class GroundednessCheckRequest(BaseModel):
    answer: str
    source_document_ids: list[str] = Field(default_factory=list)
    contexts: list[str] = Field(default_factory=list)
    question: str | None = None
    threshold: float = Field(default=0.8, ge=0.0, le=1.0)


class GroundednessCheckData(BaseModel):
    score: float
    passed: bool
    threshold: float
    fallback_required: bool
    method: str
    feedback: list[str]


class GroundednessCheckResponse(BaseModel):
    success: bool
    data: GroundednessCheckData | None = None
    error: str | None = None


def get_groundedness_checker() -> GroundednessChecker:
    return GroundednessChecker()


def get_chroma(settings: Settings = Depends(get_settings)) -> ChromaClient:
    return ChromaClient(settings)


@router.post("/groundedness/check", response_model=GroundednessCheckResponse)
def check_groundedness(
    request: GroundednessCheckRequest,
    checker: GroundednessChecker = Depends(get_groundedness_checker),
    chroma: ChromaClient = Depends(get_chroma),
) -> GroundednessCheckResponse:
    contexts = request.contexts
    if not contexts and request.source_document_ids:
        try:
            contexts = chroma.get_texts_by_document_ids(request.source_document_ids)
        except Exception as exc:
            return GroundednessCheckResponse(success=False, error=str(exc))

    result = checker.check(ServiceGroundednessRequest(
        answer=request.answer,
        contexts=contexts,
        question=request.question,
        threshold=request.threshold,
    ))
    return GroundednessCheckResponse(
        success=True,
        data=GroundednessCheckData(
            score=result.score,
            passed=result.passed,
            threshold=result.threshold,
            fallback_required=result.fallback_required,
            method=result.method,
            feedback=result.feedback,
        ),
    )
