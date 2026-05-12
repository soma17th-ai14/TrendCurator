from __future__ import annotations

import asyncio
from datetime import date, datetime
from typing import Optional

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
from app.core.scheduler_settings import create_scheduler_from_env
from app.core.settings import get_settings, get_solar_settings
from app.services.digest_generation_adapter import DigestGenerationAdapter
from app.services.digest_retriever import DailyDigestRetriever
from app.services.ingestion import IngestionService
from app.services.normalizer import normalize_documents
from app.services.scheduler import SchedulerConfig, SchedulerService

_COLLECTORS = [
    HuggingFaceDailyPapersCollector(),
    HackerNewsCollector(),
]

EXIT_SUCCESS = 0
EXIT_NOT_IMPLEMENTED = 2


async def _collect_for_date(run_date: date, config: SchedulerConfig) -> list:
    active = [c for c in _COLLECTORS if c.source_name in config.sources]
    tasks = [collector.fetch(run_date) for collector in active]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    documents = []
    for collector, result in zip(active, results):
        if isinstance(result, Exception):
            print(f"[{run_date}] {collector.source_name} 수집 실패: {result}")
            continue
        for item in result:
            documents.append(collector.normalize(item))
    return documents


def run_daily_digest_pipeline(run_date: date, config: SchedulerConfig) -> Optional[str]:
    """정기 Daily Digest 파이프라인을 실행합니다.

    후보 문서가 없으면 None을 반환하고, 생성에 성공하면 digest_id를 반환합니다.
    """
    settings = get_settings()

    # 수집 → 정규화 → 관련성 필터 → 저장
    documents = asyncio.run(_collect_for_date(run_date, config))
    if documents:
        normalized = normalize_documents(documents)
        decisions = SolarMiniRelevanceFilter().filter(normalized)
        IngestionService(
            chunker=Chunker(),
            embedder=Embedder(EmbeddingClient(settings)),
            chroma=ChromaClient(settings),
        ).ingest_batch(decisions)
        print(f"[{run_date}] 수집 {len(documents)}건 → 관련 {len(decisions)}건 저장 완료")
    else:
        print(f"[{run_date}] 수집된 문서가 없습니다.")

    retriever = Retriever(EmbeddingClient(settings), ChromaClient(settings))
    retrieval_result = DailyDigestRetriever(retriever).retrieve(
        DailyDigestRetrievalRequest(
            digest_date=run_date,
            sources=list(config.sources),  # type: ignore[arg-type]
        )
    )

    if not retrieval_result.candidates:
        print(f"[{run_date}] 후보 문서가 없어 Digest 생성을 건너뜁니다.")
        return None

    solar_settings = get_solar_settings()
    adapter = DigestGenerationAdapter(language="ko")
    generation_result = SolarProDigestGenerator.from_settings(solar_settings).generate(
        adapter.to_generation_request(retrieval_result)
    )
    return adapter.to_run_result(
        retrieval_result=retrieval_result,
        generation_result=generation_result,
    ).digest_id


def run_once(
    scheduler: SchedulerService,
    now: Optional[datetime] = None,
) -> int:
    """현재 스케줄 기준으로 Daily Digest를 한 번 실행합니다."""
    try:
        result = scheduler.run_due(run_daily_digest_pipeline, now)
    except NotImplementedError as exc:
        print(str(exc))
        return EXIT_NOT_IMPLEMENTED

    if not result.ran:
        next_run_at = scheduler.next_run_at(now).isoformat()
        print(
            "스케줄 실행 대상이 아닙니다. "
            f"reason={result.skipped_reason}, 다음 실행 예정 시각: {next_run_at}"
        )
        return EXIT_SUCCESS

    print(
        "스케줄 실행 완료: "
        f"run_date={result.run_date}, job_id={result.job_id or '없음'}"
    )
    return EXIT_SUCCESS


def main() -> int:
    scheduler = create_scheduler_from_env()
    return run_once(scheduler)


if __name__ == "__main__":
    raise SystemExit(main())
