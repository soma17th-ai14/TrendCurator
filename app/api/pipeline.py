"""데이터 수집 파이프라인 API."""

from __future__ import annotations

import asyncio
from datetime import date, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.agents.chunker import Chunker
from app.agents.embedder import Embedder
from app.agents.relevance_filter import SolarMiniRelevanceFilter
from app.core.chroma_client import ChromaClient
from app.core.embedding_client import EmbeddingClient
from app.core.settings import Settings, get_settings
from app.services.collection_status_store import CollectionStatusStore
from app.services.ingestion import IngestionService
from app.services.normalizer import normalize_documents
from app.services.scheduled_pipeline import COLLECTORS, fetch_all_documents

router = APIRouter()


class CollectRequest(BaseModel):
    date: date


class CollectData(BaseModel):
    collected_count: int
    filtered_count: int
    ingested_count: int
    skipped_count: int
    collected_at: str
    warnings: list[str] = []


class CollectResponse(BaseModel):
    success: bool
    data: CollectData | None = None
    error: str | None = None


def _build_ingestion_service(settings: Settings) -> IngestionService:
    return IngestionService(
        chunker=Chunker(),
        embedder=Embedder(EmbeddingClient(settings)),
        chroma=ChromaClient(settings),
    )


@router.post("/pipeline/collect", response_model=CollectResponse)
def collect(
    request: CollectRequest,
    settings: Settings = Depends(get_settings),
) -> CollectResponse:
    try:
        documents, fetch_warnings = asyncio.run(fetch_all_documents(request.date))

        # 모든 소스가 예외로 실패한 경우에만 전체 실패 처리
        if len(fetch_warnings) == len(COLLECTORS):
            return CollectResponse(
                success=False,
                error="모든 소스 수집 실패: " + "; ".join(fetch_warnings),
            )

        normalized = normalize_documents(documents)

        relevance_filter = SolarMiniRelevanceFilter()
        decisions = relevance_filter.filter(normalized)

        ingestion_service = _build_ingestion_service(settings)
        results = ingestion_service.ingest_batch(decisions)

        ingested = sum(1 for r in results if not r.skipped)
        skipped = sum(1 for r in results if r.skipped)

    except Exception as exc:
        return CollectResponse(success=False, error=str(exc))

    collected_at = datetime.utcnow().isoformat(timespec="seconds") + "Z"
    try:
        CollectionStatusStore(settings.collection_status_path).save_collected_at(collected_at)
    except Exception:
        pass

    return CollectResponse(
        success=True,
        data=CollectData(
            collected_count=len(documents),
            filtered_count=len(decisions),
            ingested_count=ingested,
            skipped_count=skipped,
            collected_at=collected_at,
            warnings=fetch_warnings,
        ),
    )
