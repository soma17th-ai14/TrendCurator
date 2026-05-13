"""스케줄러가 호출하는 파이프라인 실행 함수.

_COLLECTORS와 fetch_all_documents는 app/api/pipeline.py에서도 임포트하여
수집 로직이 한 곳에서만 관리되도록 합니다.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timezone

from app.agents.chunker import Chunker
from app.agents.digest_generator import SolarProDigestGenerator
from app.agents.embedder import Embedder
from app.agents.relevance_filter import SolarMiniRelevanceFilter
from app.agents.retriever import Retriever
from app.collectors.hackernews import HackerNewsCollector
from app.collectors.huggingface import HuggingFaceDailyPapersCollector
from app.core.chroma_client import ChromaClient
from app.core.embedding_client import EmbeddingClient
from app.core.models import DailyDigestRetrievalRequest
from app.core.settings import Settings, get_settings, get_solar_settings
from app.services.collection_status_store import CollectionStatusStore
from app.services.digest_generation_adapter import DigestGenerationAdapter
from app.services.digest_retriever import DailyDigestRetriever
from app.services.digest_store import FileDigestStore
from app.services.groundedness import GroundednessCheckRequest, GroundednessChecker
from app.services.ingestion import IngestionService
from app.services.normalizer import normalize_documents
from app.services.profile_store import FileProfileStore
from app.services.scheduler import SchedulerConfig

logger = logging.getLogger(__name__)

COLLECTORS = [
    HuggingFaceDailyPapersCollector(),
    HackerNewsCollector(),
]


async def fetch_all_documents(target_date: date) -> tuple[list, list[str]]:
    """모든 소스에서 문서를 병렬 수집하고 (documents, warnings) 를 반환합니다."""
    tasks = [collector.fetch(target_date) for collector in COLLECTORS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    documents = []
    warnings = []
    for collector, result in zip(COLLECTORS, results):
        if isinstance(result, Exception):
            warnings.append(f"{collector.__class__.__name__} 수집 실패: {result}")
            continue
        for item in result:
            documents.append(collector.normalize(item))
    return documents, warnings


def run_pipeline(run_date: date, config: SchedulerConfig) -> str | None:
    """수집 → 인제스트 → 다이제스트 생성 전체 파이프라인을 실행합니다."""
    settings: Settings = get_settings()

    # 1. 수집
    try:
        documents, warnings = asyncio.run(fetch_all_documents(run_date))
    except Exception as exc:
        logger.error("스케줄러: 수집 단계 실패 (%s)", exc)
        return None

    if len(warnings) == len(COLLECTORS):
        logger.error("스케줄러: 모든 소스 수집 실패 — %s", "; ".join(warnings))
        return None

    if warnings:
        logger.warning("스케줄러: 일부 소스 수집 실패 — %s", "; ".join(warnings))

    # 2. 정규화 → 관련성 필터 → 인제스트
    try:
        normalized = normalize_documents(documents)
        decisions = SolarMiniRelevanceFilter().filter(normalized)
        ingestion = IngestionService(
            chunker=Chunker(),
            embedder=Embedder(EmbeddingClient(settings)),
            chroma=ChromaClient(settings),
        )
        results = ingestion.ingest_batch(decisions)
        ingested = sum(1 for r in results if not r.skipped)
        logger.info("스케줄러: %d건 수집, %d건 인제스트 완료", len(documents), ingested)

        collected_at = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
        CollectionStatusStore(settings.collection_status_path).save_collected_at(collected_at)
    except Exception as exc:
        logger.error("스케줄러: 인제스트 단계 실패 (%s)", exc)
        return None

    # 3. 다이제스트 생성
    try:
        profile_store = FileProfileStore(settings.profile_data_path)
        profile = profile_store.load()
        keywords = profile.keywords if profile else ["LangGraph", "Multi-agent", "RAG"]
        language = profile.language if profile else "ko"

        retriever = Retriever(ChromaClient(settings))
        retrieval = DailyDigestRetriever(retriever).retrieve(DailyDigestRetrievalRequest(
            digest_date=run_date,
            top_k=10,
            profile_based=True,
            keywords=keywords,
            sources=list(config.sources),
        ))

        adapter = DigestGenerationAdapter(language=language)
        generation_request = adapter.to_generation_request(retrieval, profile_keywords=keywords)

        try:
            generator = SolarProDigestGenerator.from_settings(get_solar_settings())
            generation_result = generator.generate(generation_request)
        except Exception as gen_exc:
            logger.warning("스케줄러: LLM 생성 실패, fallback 사용 (%s)", gen_exc)
            generation_result = _fallback_digest(generation_request)

        grounding = GroundednessChecker().check(GroundednessCheckRequest(
            answer=" ".join(item.summary for item in generation_result.items),
            contexts=[c.content for c in retrieval.candidates],
        ))
        generation_result.groundedness_score = grounding.score

        run_result = adapter.to_run_result(
            retrieval_result=retrieval,
            generation_result=generation_result,
        )
        FileDigestStore(settings.digest_data_path).save(run_result)
        logger.info("스케줄러: 다이제스트 저장 완료 — %s", run_result.digest_id)
        return run_result.digest_id

    except Exception as exc:
        logger.error("스케줄러: 다이제스트 생성 실패 (%s)", exc)
        return None


def _fallback_digest(request):
    from app.core.models import DigestItem, SolarProDigestGenerationResult

    return SolarProDigestGenerationResult(
        digest_id=f"digest_{request.digest_date:%Y%m%d}",
        date=request.digest_date,
        title="AI Agent Daily Digest",
        groundedness_score=0.0,
        items=[
            DigestItem(
                document_id=c.document_id,
                title=c.title,
                source=c.source,
                url=c.url,
                published_at=c.published_at,
                summary=c.summary_preview or c.content[:240],
                key_points=[c.summary_preview or c.content[:160]],
                contribution="Not stated in source",
                benchmark="Not stated in source",
                critique="Not stated in source",
                tags=c.tags or c.matched_keywords,
                evidence_document_ids=[c.document_id],
                llm_model="solar-pro-3",
            )
            for c in request.candidates
        ],
    )
