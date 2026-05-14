"""Daily Digest generation API."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.responses import ErrorResponse, error_response
from app.core.settings import Settings, get_settings
from app.services.digest_store import DigestStoreError, FileDigestStore
from app.services.profile_store import FileProfileStore
from app.services.scheduled_pipeline import regenerate_digest

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


def get_profile_store(settings: Settings = Depends(get_settings)) -> FileProfileStore:
    return FileProfileStore(settings.profile_data_path)


@router.post("/digest/generate", response_model=DigestGenerateResponse)
def generate_digest(
    request: DigestGenerateRequest,
    store: FileDigestStore = Depends(get_digest_store),
    profile_store: FileProfileStore = Depends(get_profile_store),
) -> DigestGenerateResponse:
    """수동 재생성 엔드포인트.

    스케줄러 파이프라인과 동일한 락/재시도/한국어 fallback 을 공유하기 위해
    ``scheduled_pipeline.regenerate_digest`` 를 호출합니다. 수집/인제스트 단계는
    포함하지 않으며, ChromaDB 에 이미 색인된 데이터를 대상으로 다이제스트만 다시
    생성합니다.
    """
    try:
        keywords = request.keywords
        language = "ko"
        if request.profile_based:
            profile = profile_store.load()
            if profile is not None:
                keywords = profile.keywords
                language = profile.language

        digest_id = regenerate_digest(
            request.date,
            sources=["huggingface", "hackernews"],
            keywords=keywords,
            language=language,
            top_k=request.top_k,
        )
        run_result = store.get(digest_id)
        if run_result is None:
            return DigestGenerateResponse(
                success=False,
                error=error_response(
                    "DIGEST_GENERATION_FAILED",
                    f"재생성된 다이제스트를 다시 불러올 수 없습니다: {digest_id}",
                ),
            )
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
