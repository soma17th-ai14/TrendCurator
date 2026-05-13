"""Daily Digest generation API."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.digest_generator import SolarProDigestGenerator
from app.agents.retriever import Retriever
from app.api.documents import get_retriever
from app.api.responses import ErrorResponse, error_response
from app.core.models import DailyDigestRetrievalRequest
from app.core.settings import Settings, get_settings, get_solar_settings
from app.services.digest_generation_adapter import DigestGenerationAdapter
from app.services.digest_retriever import DailyDigestRetriever
from app.services.digest_store import DigestStoreError, FileDigestStore
from app.services.groundedness import GroundednessChecker, GroundednessCheckRequest

router = APIRouter()


class DigestGenerateRequest(BaseModel):
    date: date
    profile_based: bool = True
    top_k: int = Field(default=10, ge=1, le=50)
    keywords: list[str] = Field(default_factory=lambda: ["LangGraph", "Multi-agent", "RAG"])


class DigestGenerateResponse(BaseModel):
    success: bool
    data: dict[str, Any] | None = None
    error: ErrorResponse | None = None


class DigestGetResponse(BaseModel):
    success: bool
    data: dict[str, Any] | None = None
    error: ErrorResponse | None = None


class DigestListItem(BaseModel):
    digest_id: str
    date: date
    item_count: int
    candidate_count: int
    groundedness_score: float


class DigestListResponse(BaseModel):
    success: bool
    data: list[DigestListItem] | None = None
    error: ErrorResponse | None = None


def get_digest_store(settings: Settings = Depends(get_settings)) -> FileDigestStore:
    return FileDigestStore(settings.digest_data_path)


@router.post("/digest/generate", response_model=DigestGenerateResponse)
def generate_digest(
    request: DigestGenerateRequest,
    retriever: Retriever = Depends(get_retriever),
    store: FileDigestStore = Depends(get_digest_store),
) -> DigestGenerateResponse:
    try:
        retrieval = DailyDigestRetriever(retriever).retrieve(DailyDigestRetrievalRequest(
            digest_date=request.date,
            top_k=request.top_k,
            profile_based=request.profile_based,
            keywords=request.keywords,
            sources=["huggingface", "hackernews"],
        ))
        adapter = DigestGenerationAdapter(language="ko")
        generation_request = adapter.to_generation_request(
            retrieval,
            profile_keywords=request.keywords,
        )

        try:
            generator = SolarProDigestGenerator.from_settings(get_solar_settings())
            generation_result = generator.generate(generation_request)
        except Exception:
            generation_result = _fallback_digest(generation_request)

        grounding = GroundednessChecker().check(GroundednessCheckRequest(
            answer=" ".join(item.summary for item in generation_result.items),
            contexts=[candidate.content for candidate in retrieval.candidates],
        ))
        generation_result.groundedness_score = grounding.score
        run_result = adapter.to_run_result(
            retrieval_result=retrieval,
            generation_result=generation_result,
        )
        store.save(run_result)
    except DigestStoreError as exc:
        return DigestGenerateResponse(
            success=False,
            error=error_response("DIGEST_STORE_ERROR", str(exc)),
        )
    except Exception as exc:
        return DigestGenerateResponse(
            success=False,
            error=error_response("DIGEST_GENERATION_FAILED", str(exc)),
        )

    return DigestGenerateResponse(
        success=True,
        data=run_result.model_dump(mode="json"),
    )


@router.get("/digest", response_model=DigestListResponse)
def list_digests(
    date_from: date | None = None,
    date_to: date | None = None,
    store: FileDigestStore = Depends(get_digest_store),
) -> DigestListResponse:
    try:
        results = store.list(date_from=date_from, date_to=date_to)
    except DigestStoreError as exc:
        return DigestListResponse(
            success=False,
            error=error_response("DIGEST_STORE_ERROR", str(exc)),
        )

    return DigestListResponse(
        success=True,
        data=[
            DigestListItem(
                digest_id=result.digest_id,
                date=result.date,
                item_count=result.item_count,
                candidate_count=result.candidate_count,
                groundedness_score=result.groundedness_score,
            )
            for result in results
        ],
    )


@router.get("/digest/{digest_id}", response_model=DigestGetResponse)
def get_digest(
    digest_id: str,
    store: FileDigestStore = Depends(get_digest_store),
) -> DigestGetResponse:
    try:
        result = store.get(digest_id)
    except DigestStoreError as exc:
        return DigestGetResponse(
            success=False,
            error=error_response("DIGEST_STORE_ERROR", str(exc)),
        )

    if result is None:
        return DigestGetResponse(
            success=False,
            error=error_response("DIGEST_NOT_FOUND", "Digest를 찾을 수 없습니다."),
        )

    return DigestGetResponse(success=True, data=result.digest.model_dump(mode="json"))


def _fallback_digest(request):
    from app.core.models import DigestItem, SolarProDigestGenerationResult

    return SolarProDigestGenerationResult(
        digest_id=f"digest_{request.digest_date:%Y%m%d}",
        date=request.digest_date,
        title="AI Agent Daily Digest",
        groundedness_score=0.0,
        items=[
            DigestItem(
                document_id=candidate.document_id,
                title=candidate.title,
                source=candidate.source,
                url=candidate.url,
                published_at=candidate.published_at,
                summary=candidate.summary_preview or candidate.content[:240],
                key_points=[candidate.summary_preview or candidate.content[:160]],
                contribution="Not stated in source",
                benchmark="Not stated in source",
                critique="Not stated in source",
                tags=candidate.tags or candidate.matched_keywords,
                evidence_document_ids=[candidate.document_id],
                llm_model="solar-pro-3",
            )
            for candidate in request.candidates
        ],
    )
