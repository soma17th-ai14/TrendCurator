"""스케줄러 파이프라인(run_pipeline) 실패 전파 동작 테스트."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import pytest

from app.services import scheduled_pipeline
from app.services.scheduled_pipeline import PipelineRunError, run_pipeline
from app.core.models import DigestCandidate, SolarProDigestGenerationRequest
from app.services.scheduler import (
    SchedulerConfig,
    SchedulerService,
    SchedulerState,
)


class _FailingCollector:
    source_name = "huggingface"

    async def fetch(self, target_date: date) -> list[Any]:
        raise RuntimeError("의도적 수집 실패")

    def normalize(self, item: Any) -> Any:  # pragma: no cover - fetch가 먼저 실패
        return item


class _EmptyCollector:
    """경고 없이 빈 결과를 반환하는 수집기."""

    source_name = "huggingface"

    async def fetch(self, target_date: date) -> list[Any]:
        return []

    def normalize(self, item: Any) -> Any:  # pragma: no cover - 빈 결과
        return item


def _config(sources: tuple[str, ...] = ("huggingface",)) -> SchedulerConfig:
    return SchedulerConfig(enabled=True, time="00:01", timezone="UTC", sources=sources)


def test_run_pipeline_raises_when_collection_stage_fails(monkeypatch):
    """수집 단계 자체가 예외를 던지면 PipelineRunError로 전파한다."""

    async def boom(target_date: date, sources: list[str] | None = None):
        raise RuntimeError("network down")

    monkeypatch.setattr(scheduled_pipeline, "fetch_all_documents", boom)

    with pytest.raises(PipelineRunError):
        run_pipeline(date(2026, 5, 14), _config())


def test_run_pipeline_raises_when_all_sources_fail(monkeypatch):
    """선택된 모든 소스가 실패하면 PipelineRunError를 raise하여 재시도를 허용한다."""
    monkeypatch.setattr(scheduled_pipeline, "COLLECTORS", [_FailingCollector()])

    with pytest.raises(PipelineRunError):
        run_pipeline(date(2026, 5, 14), _config(sources=("huggingface",)))


def test_run_due_does_not_update_last_run_at_when_runner_raises():
    """런너가 PipelineRunError를 던지면 last_run_at이 갱신되지 않아야 한다.

    이 동작이 보장돼야 일시적 장애 시 동일 일자 안에서 다음 점검 사이클이 재시도된다.
    """

    def failing_runner(run_date: date, config: SchedulerConfig) -> str | None:
        raise PipelineRunError("intentional")

    service = SchedulerService(SchedulerState(config=_config()))
    fixed_now = datetime(2026, 5, 14, 1, 0, tzinfo=timezone.utc)

    with pytest.raises(PipelineRunError):
        service.run_due(failing_runner, now=fixed_now)

    assert service.state.last_run_at is None


def test_run_due_updates_last_run_at_on_success():
    """대비 케이스 — 정상 완료 시에는 last_run_at이 갱신된다."""

    def ok_runner(run_date: date, config: SchedulerConfig) -> str | None:
        return "digest_20260514"

    service = SchedulerService(SchedulerState(config=_config()))
    fixed_now = datetime(2026, 5, 14, 1, 0, tzinfo=timezone.utc)

    result = service.run_due(ok_runner, now=fixed_now)

    assert result.ran is True
    assert result.job_id == "digest_20260514"
    assert service.state.last_run_at is not None


def test_fallback_digest_uses_korean_placeholders():
    candidate = DigestCandidate(
        document_id="doc_001",
        source="huggingface",
        title="PyRAG: Programmatic Retrieval Augmented Generation",
        url="https://example.com/pyrag",
        published_at=date(2026, 5, 14),
        content=(
            "ly with how code-specialized language models are trained to operate. "
            "Motivated by this, we introduce PyRAG."
        ),
        summary_preview=(
            "ly with how code-specialized language models are trained to operate. "
            "Motivated by this, we introduce PyRAG."
        ),
        similarity_score=0.9,
        relevance_score=0.9,
        matched_keywords=["RAG", "program synthesis"],
        tags=[],
    )
    request = SolarProDigestGenerationRequest(
        digest_date=date(2026, 5, 14),
        language="ko",
        candidates=[candidate],
    )

    result = scheduled_pipeline._fallback_digest(request)
    item = result.items[0]

    assert item.summary.startswith("PyRAG: Programmatic Retrieval Augmented Generation 문서에서 확인된 내용입니다.")
    assert item.contribution == "명시된 근거 없음"
    assert item.benchmark == "명시된 근거 없음"
    assert item.critique == "명시된 근거 없음"
    assert "Not stated in source" not in item.model_dump_json()
