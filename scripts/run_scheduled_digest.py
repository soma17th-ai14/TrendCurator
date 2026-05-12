from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from app.agents.digest_generator import SolarProDigestGenerator
from app.agents.retriever import Retriever
from app.core.chroma_client import ChromaClient
from app.core.embedding_client import EmbeddingClient
from app.core.models import DailyDigestRetrievalRequest
from app.core.scheduler_settings import create_scheduler_from_env
from app.core.settings import get_settings, get_solar_settings
from app.services.digest_generation_adapter import DigestGenerationAdapter
from app.services.digest_retriever import DailyDigestRetriever
from app.services.scheduler import SchedulerConfig, SchedulerService


EXIT_SUCCESS = 0
EXIT_NOT_IMPLEMENTED = 2


def run_daily_digest_pipeline(run_date: date, config: SchedulerConfig) -> Optional[str]:
    """정기 Daily Digest 파이프라인을 실행합니다.

    후보 문서가 없으면 None을 반환하고, 생성에 성공하면 digest_id를 반환합니다.
    """
    solar_settings = get_solar_settings()
    settings = get_settings()

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
