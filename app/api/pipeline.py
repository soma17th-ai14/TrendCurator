"""데이터 수집 파이프라인 API."""

from __future__ import annotations

import asyncio
from datetime import date, datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.agents.chunker import Chunker
from app.agents.embedder import Embedder
from app.agents.relevance_filter import SolarMiniRelevanceFilter
from app.collectors.hackernews import HackerNewsCollector
from app.collectors.huggingface import HuggingFaceDailyPapersCollector
from app.core.chroma_client import ChromaClient
from app.core.embedding_client import EmbeddingClient
from app.core.settings import Settings, get_settings
from app.services.ingestion import IngestionService
from app.services.normalizer import normalize_documents

router = APIRouter()

_COLLECTORS = [
    HuggingFaceDailyPapersCollector(),
    HackerNewsCollector(),
]


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


async def _fetch_all(target_date: date) -> tuple[list, list[str]]:
    tasks = [collector.fetch(target_date) for collector in _COLLECTORS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    documents = []
    warnings = []
    for collector, result in zip(_COLLECTORS, results):
        if isinstance(result, Exception):
            warnings.append(f"{collector.__class__.__name__} 수집 실패: {result}")
            continue
        for item in result:
            documents.append(collector.normalize(item))
    return documents, warnings


@router.post("/pipeline/collect", response_model=CollectResponse)
def collect(
    request: CollectRequest,
    settings: Settings = Depends(get_settings),
) -> CollectResponse:
    try:
        documents, fetch_warnings = asyncio.run(_fetch_all(request.date))

        if not documents and fetch_warnings:
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

    return CollectResponse(
        success=True,
        data=CollectData(
            collected_count=len(documents),
            filtered_count=len(decisions),
            ingested_count=ingested,
            skipped_count=skipped,
            collected_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
            warnings=fetch_warnings,
        ),
    )
