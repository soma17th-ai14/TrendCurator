"""스케줄러가 호출하는 파이프라인 실행 함수.

_COLLECTORS와 fetch_all_documents는 app/api/pipeline.py에서도 임포트하여
수집 로직이 한 곳에서만 관리되도록 합니다.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import date, datetime, timedelta, timezone

from app.agents.chunker import Chunker
from app.agents.digest_generator import SolarProDigestGenerator
from app.agents.embedder import Embedder
from app.agents.solar_relevance_filter import build_solar_mini_relevance_filter
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
from app.services.scheduler import SchedulerConfig, effective_digest_date

logger = logging.getLogger(__name__)

# Solar Pro 다이제스트 생성 실패 시 재시도 횟수.
# 일시적 네트워크/쿼터 오류를 흡수하되, 영구적 오류(인증·파서 등)에서는 빠르게 fallback 으로 넘어가도록
# 보수적으로 3회로 둡니다. 모두 실패하면 `_fallback_digest()` 가 한국어 placeholder 결과를 만듭니다.
_SOLAR_PRO_MAX_ATTEMPTS = 3
_SOLAR_PRO_RETRY_BACKOFF_SECONDS = 2.0

# 같은 문서가 연이은 다이제스트에서 다시 1위로 뽑히는 것을 막기 위해, 이전 N일 다이제스트에 선정됐던
# document_id 를 후보 풀에서 제외합니다. lookback_days(1) 보다 1 더 길게 잡아 게시일이 살짝 늦게
# 잡힌 문서도 다음 날 디지스트에서 다시 등장하지 않도록 합니다.
_DIGEST_DEDUP_LOOKBACK_DAYS = 2


class PipelineRunError(RuntimeError):
    """스케줄러가 호출한 파이프라인이 복구 가능한 hard failure로 종료될 때 발생합니다.

    예외가 전파되면 ``SchedulerService.run_due`` 가 ``last_run_at`` 을 갱신하지 않으므로
    동일 일자 내 다음 점검 사이클에서 재시도가 가능합니다. ``None`` 반환은 "정상적으로
    실행 완료"로 해석되어 그날 재시도가 불가능해지므로 사용하지 않습니다.
    """


COLLECTORS = [
    HuggingFaceDailyPapersCollector(),
    HackerNewsCollector(),
]


async def fetch_all_documents(
    target_date: date,
    sources: list[str] | None = None,
) -> tuple[list, list[str]]:
    """지정된 소스에서 문서를 병렬 수집하고 (documents, warnings) 를 반환합니다.

    sources가 None이면 COLLECTORS 전체를 사용합니다.
    """
    active = [c for c in COLLECTORS if sources is None or c.source_name in sources]
    tasks = [collector.fetch(target_date) for collector in active]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    documents = []
    warnings = []
    for collector, result in zip(active, results):
        if isinstance(result, Exception):
            warnings.append(f"{collector.__class__.__name__} 수집 실패: {result}")
            continue
        for item in result:
            documents.append(collector.normalize(item))
    return documents, warnings


def run_pipeline(run_date: date, config: SchedulerConfig) -> str | None:
    """수집 → 인제스트 → 다이제스트 생성 전체 파이프라인을 실행합니다.

    실패 시 ``PipelineRunError`` 를 raise합니다. 이는 ``SchedulerService.run_due`` 에서
    ``last_run_at`` 갱신을 막아 동일 일자 내 재시도를 허용합니다.
    """
    settings: Settings = get_settings()

    # 1. 수집
    active_sources = list(config.sources)
    try:
        documents, warnings = asyncio.run(fetch_all_documents(run_date, sources=active_sources))
    except Exception as exc:
        logger.error("스케줄러: 수집 단계 실패 (%s)", exc)
        raise PipelineRunError(f"수집 단계 실패: {exc}") from exc

    if active_sources and len(warnings) == len(active_sources):
        logger.error("스케줄러: 모든 소스 수집 실패 — %s", "; ".join(warnings))
        raise PipelineRunError("모든 소스 수집 실패: " + "; ".join(warnings))

    if warnings:
        logger.warning("스케줄러: 일부 소스 수집 실패 — %s", "; ".join(warnings))

    # 2. 정규화 → 관련성 필터 → 인제스트
    try:
        normalized = normalize_documents(documents)
        decisions = build_solar_mini_relevance_filter(settings).filter(normalized)
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
        raise PipelineRunError(f"인제스트 단계 실패: {exc}") from exc

    # 3. 다이제스트 생성
    try:
        profile_store = FileProfileStore(settings.profile_data_path)
        profile = profile_store.load()
        keywords = profile.keywords if profile else ["LangGraph", "Multi-agent", "RAG"]
        language = profile.language if profile else "ko"

        retriever = Retriever(EmbeddingClient(settings), ChromaClient(settings))
        digest_store = FileDigestStore(settings.digest_data_path)
        exclude_document_ids = _collect_recent_digest_document_ids(
            digest_store, run_date, lookback_days=_DIGEST_DEDUP_LOOKBACK_DAYS
        )
        retrieval = DailyDigestRetriever(retriever).retrieve(DailyDigestRetrievalRequest(
            digest_date=run_date,
            top_k=10,
            profile_based=True,
            keywords=keywords,
            sources=list(config.sources),
            exclude_document_ids=exclude_document_ids,
        ))

        adapter = DigestGenerationAdapter(language=language)
        generation_request = adapter.to_generation_request(retrieval, profile_keywords=keywords)

        generation_result = _generate_with_retry(generation_request)

        grounding = GroundednessChecker().check(GroundednessCheckRequest(
            answer=" ".join(item.summary for item in generation_result.items),
            contexts=[c.content for c in retrieval.candidates],
        ))
        generation_result.groundedness_score = grounding.score

        run_result = adapter.to_run_result(
            retrieval_result=retrieval,
            generation_result=generation_result,
        )
        digest_store.save(run_result)
        logger.info("스케줄러: 다이제스트 저장 완료 — %s", run_result.digest_id)
        return run_result.digest_id

    except Exception as exc:
        logger.error("스케줄러: 다이제스트 생성 실패 (%s)", exc)
        raise PipelineRunError(f"다이제스트 생성 실패: {exc}") from exc


def run_startup_digest(config: SchedulerConfig) -> str | None:
    """앱 부팅 직후 효력 일자 기준 다이제스트가 없으면 즉시 생성합니다.

    스케줄러 루프와 별개의 진입점으로, 효력 일자(``effective_digest_date``) 기준 다이제스트가
    이미 존재하면 아무 일도 하지 않고 ``None`` 을 반환합니다. 없으면 ``run_pipeline`` 을
    동기 호출하고 생성된 ``digest_id`` 를 반환합니다.

    실패 시 ``PipelineRunError`` 를 raise 하지 않고 ``None`` 을 반환합니다. 부팅 자동 실행은
    스케줄러의 일일 마크업과 분리되어 있어, 실패하더라도 정상 스케줄 사이클에서 재시도되기
    때문입니다.
    """
    target_date = effective_digest_date(config)
    digest_id = f"digest_{target_date:%Y%m%d}"

    try:
        settings: Settings = get_settings()
        store = FileDigestStore(settings.digest_data_path)
        if store.get(digest_id) is not None:
            logger.info("부팅 자동 실행: 효력 일자 다이제스트가 이미 존재합니다 — %s", digest_id)
            return None
    except Exception as exc:
        logger.warning("부팅 자동 실행: 기존 다이제스트 조회 실패 — %s", exc)

    logger.info("부팅 자동 실행: 효력 일자 다이제스트 생성 시작 — %s", target_date)
    try:
        return run_pipeline(target_date, config)
    except PipelineRunError as exc:
        logger.warning("부팅 자동 실행: 다이제스트 생성 실패 (%s) — 정상 스케줄 사이클에서 재시도됩니다.", exc)
        return None


def demo_bootstrap_dates(
    config: SchedulerConfig,
    *,
    days: int = 5,
    now: datetime | None = None,
) -> list[date]:
    """Return previous digest dates for demo startup backfill."""
    if days <= 0:
        return []

    end_date = effective_digest_date(config, now=now)
    start_date = end_date - timedelta(days=days)
    return [start_date + timedelta(days=offset) for offset in range(days)]


def run_demo_bootstrap(config: SchedulerConfig, *, days: int = 5) -> list[str]:
    """Generate missing digests for the previous ``days`` dates."""
    if days <= 0:
        logger.info("demo bootstrap: skipped because days=%d", days)
        return []

    settings: Settings = get_settings()
    store = FileDigestStore(settings.digest_data_path)
    generated: list[str] = []

    for target_date in demo_bootstrap_dates(config, days=days):
        digest_id = f"digest_{target_date:%Y%m%d}"
        try:
            if store.get(digest_id) is not None:
                logger.info("demo bootstrap: digest already exists, skipped %s", digest_id)
                continue
        except Exception as exc:
            logger.warning("demo bootstrap: failed to inspect %s (%s), running pipeline", digest_id, exc)

        logger.info("demo bootstrap: generating %s", digest_id)
        try:
            result = run_pipeline(target_date, config)
        except PipelineRunError as exc:
            logger.warning("demo bootstrap: failed to generate %s (%s)", digest_id, exc)
            continue

        if result is not None:
            generated.append(result)

    logger.info("demo bootstrap: generated %d digest(s)", len(generated))
    return generated


def _collect_recent_digest_document_ids(
    store: FileDigestStore,
    run_date: date,
    *,
    lookback_days: int,
) -> list[str]:
    """직전 ``lookback_days`` 일자의 다이제스트에서 선정된 문서 id 들을 모아 중복 제거 후 반환합니다.

    저장소 조회 실패는 fatal 이 아닙니다 — 중복 제거는 디지스트 품질 개선 목적이지 정확성 보장은 아니므로,
    조회 실패 시 빈 리스트로 fallback 하여 파이프라인 자체는 계속 진행시킵니다.
    """
    if lookback_days <= 0:
        return []

    collected: list[str] = []
    seen: set[str] = set()
    for offset in range(1, lookback_days + 1):
        prev_date = run_date - timedelta(days=offset)
        digest_id = f"digest_{prev_date:%Y%m%d}"
        try:
            prev = store.get(digest_id)
        except Exception as exc:
            logger.warning(
                "다이제스트 중복 제거: 이전 다이제스트 조회 실패 — %s (%s)", digest_id, exc
            )
            continue
        if prev is None:
            continue
        for doc_id in prev.source_document_ids:
            if doc_id and doc_id not in seen:
                seen.add(doc_id)
                collected.append(doc_id)
    if collected:
        logger.info(
            "다이제스트 중복 제거: 직전 %d일 다이제스트의 %d개 문서를 후보에서 제외합니다.",
            lookback_days,
            len(collected),
        )
    return collected


def _generate_with_retry(generation_request):
    """Solar Pro 다이제스트 생성을 재시도하고, 모두 실패하면 fallback 결과를 반환합니다.

    무한 루프를 피하기 위해 시도 횟수를 제한하며, 각 실패 사이에 짧은 백오프를 둡니다.
    영구적인 오류(인증/쿼터/파서)인 경우에도 ``_SOLAR_PRO_MAX_ATTEMPTS`` 회만에 fallback 으로 넘어갑니다.
    """
    last_exc: Exception | None = None
    for attempt in range(1, _SOLAR_PRO_MAX_ATTEMPTS + 1):
        try:
            generator = SolarProDigestGenerator.from_settings(get_solar_settings())
            return generator.generate(generation_request)
        except Exception as gen_exc:
            last_exc = gen_exc
            if attempt < _SOLAR_PRO_MAX_ATTEMPTS:
                logger.warning(
                    "스케줄러: LLM 생성 실패 (시도 %d/%d, %s) — 재시도합니다.",
                    attempt,
                    _SOLAR_PRO_MAX_ATTEMPTS,
                    gen_exc,
                )
                time.sleep(_SOLAR_PRO_RETRY_BACKOFF_SECONDS * attempt)
            else:
                logger.warning(
                    "스케줄러: LLM 생성 %d회 모두 실패 (%s) — fallback 사용.",
                    _SOLAR_PRO_MAX_ATTEMPTS,
                    gen_exc,
                )
    assert last_exc is not None
    return _fallback_digest(generation_request)


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
                summary=_fallback_summary(c),
                key_points=_fallback_key_points(c),
                contribution="명시된 근거 없음",
                benchmark="명시된 근거 없음",
                critique="명시된 근거 없음",
                tags=c.tags or c.matched_keywords,
                evidence_document_ids=[c.document_id],
                llm_model="solar-pro-3",
            )
            for c in request.candidates
        ],
    )


def _fallback_summary(candidate) -> str:
    title = candidate.title.strip()
    preview = _clean_preview(candidate.summary_preview or candidate.content)
    if preview:
        return f"{title} 문서에서 확인된 내용입니다. {preview}"
    return f"{title} 문서입니다. 상세 요약은 Solar Pro 생성이 재시도되면 보강됩니다."


def _fallback_key_points(candidate) -> list[str]:
    points = [f"문서 제목: {candidate.title.strip()}"]
    keywords = candidate.tags or candidate.matched_keywords
    if keywords:
        points.append("관련 키워드: " + ", ".join(keywords[:4]))
    if candidate.published_at is not None:
        points.append(f"게시일: {candidate.published_at.isoformat()}")
    return points


def _clean_preview(text: str, limit: int = 220) -> str:
    compact = " ".join(text.split())
    if not compact:
        return ""
    compact = compact[:limit].strip()
    sentence_end = max(compact.rfind("."), compact.rfind("!"), compact.rfind("?"))
    if sentence_end >= 80:
        compact = compact[: sentence_end + 1]
    return compact
