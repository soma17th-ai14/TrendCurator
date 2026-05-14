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


class _EmptyDigestStore:
    """run_pipeline 의 early-return 가드를 우회하기 위한 stub. 항상 '없음'을 반환합니다."""

    def get(self, _digest_id):
        return None


@pytest.fixture
def stub_empty_digest_store(monkeypatch):
    monkeypatch.setattr(
        scheduled_pipeline, "FileDigestStore", lambda _path: _EmptyDigestStore()
    )


def test_run_pipeline_raises_when_collection_stage_fails(monkeypatch, stub_empty_digest_store):
    """수집 단계 자체가 예외를 던지면 PipelineRunError로 전파한다."""

    async def boom(target_date: date, sources: list[str] | None = None):
        raise RuntimeError("network down")

    monkeypatch.setattr(scheduled_pipeline, "fetch_all_documents", boom)

    with pytest.raises(PipelineRunError):
        run_pipeline(date(2026, 5, 14), _config())


def test_run_pipeline_raises_when_all_sources_fail(monkeypatch, stub_empty_digest_store):
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


def test_generate_with_retry_returns_first_success(monkeypatch):
    """첫 시도가 성공하면 추가 호출 없이 결과를 반환한다."""
    calls = {"count": 0}

    class _OkGenerator:
        @classmethod
        def from_settings(cls, _settings):
            return cls()

        def generate(self, _request):
            calls["count"] += 1
            return "ok-result"

    monkeypatch.setattr(scheduled_pipeline, "SolarProDigestGenerator", _OkGenerator)
    monkeypatch.setattr(scheduled_pipeline, "get_solar_settings", lambda: object())

    assert scheduled_pipeline._generate_with_retry(object()) == "ok-result"
    assert calls["count"] == 1


def test_generate_with_retry_recovers_after_transient_failure(monkeypatch):
    """일시 실패 후 재시도 성공 시 fallback 으로 빠지지 않는다."""
    calls = {"count": 0}

    class _FlakyGenerator:
        @classmethod
        def from_settings(cls, _settings):
            return cls()

        def generate(self, _request):
            calls["count"] += 1
            if calls["count"] < 2:
                raise RuntimeError("transient")
            return "recovered"

    monkeypatch.setattr(scheduled_pipeline, "SolarProDigestGenerator", _FlakyGenerator)
    monkeypatch.setattr(scheduled_pipeline, "get_solar_settings", lambda: object())
    monkeypatch.setattr(scheduled_pipeline.time, "sleep", lambda _s: None)

    assert scheduled_pipeline._generate_with_retry(object()) == "recovered"
    assert calls["count"] == 2


def test_generate_with_retry_falls_back_after_max_attempts(monkeypatch):
    """최대 시도 횟수 후에도 실패하면 한국어 fallback 결과를 반환한다."""
    calls = {"count": 0}

    class _BrokenGenerator:
        @classmethod
        def from_settings(cls, _settings):
            return cls()

        def generate(self, _request):
            calls["count"] += 1
            raise RuntimeError("permanent")

    sentinel = object()

    monkeypatch.setattr(scheduled_pipeline, "SolarProDigestGenerator", _BrokenGenerator)
    monkeypatch.setattr(scheduled_pipeline, "get_solar_settings", lambda: object())
    monkeypatch.setattr(scheduled_pipeline, "_fallback_digest", lambda _req: sentinel)
    monkeypatch.setattr(scheduled_pipeline.time, "sleep", lambda _s: None)

    assert scheduled_pipeline._generate_with_retry(object()) is sentinel
    assert calls["count"] == scheduled_pipeline._SOLAR_PRO_MAX_ATTEMPTS


class _StubDigestStore:
    """``_collect_recent_digest_document_ids`` 가 호출하는 ``get(digest_id)`` 만 구현한 페이크."""

    def __init__(self, entries: dict[str, list[str]] | None = None) -> None:
        self._entries = entries or {}

    def get(self, digest_id: str):
        doc_ids = self._entries.get(digest_id)
        if doc_ids is None:
            return None

        class _Result:
            def __init__(self, ids: list[str]) -> None:
                self.source_document_ids = ids

        return _Result(doc_ids)


def test_collect_recent_digest_document_ids_aggregates_and_dedupes():
    """직전 N일 다이제스트의 source_document_ids 를 합집합으로 모으고, 중복은 한 번만 포함한다."""
    store = _StubDigestStore(
        {
            "digest_20260513": ["doc_a", "doc_b"],
            "digest_20260512": ["doc_b", "doc_c"],
        }
    )

    result = scheduled_pipeline._collect_recent_digest_document_ids(
        store, date(2026, 5, 14), lookback_days=2
    )

    assert set(result) == {"doc_a", "doc_b", "doc_c"}
    assert len(result) == 3


def test_collect_recent_digest_document_ids_returns_empty_when_no_history():
    """이전 다이제스트가 없으면 빈 리스트를 반환한다."""
    result = scheduled_pipeline._collect_recent_digest_document_ids(
        _StubDigestStore(), date(2026, 5, 14), lookback_days=2
    )
    assert result == []


def test_collect_recent_digest_document_ids_handles_store_errors():
    """저장소 조회가 실패해도 다른 일자는 계속 시도하고 fatal 하지 않다."""

    class _PartiallyBrokenStore:
        def get(self, digest_id: str):
            if digest_id.endswith("13"):
                raise RuntimeError("disk error")
            return _StubDigestStore({"digest_20260512": ["doc_c"]}).get(digest_id)

    result = scheduled_pipeline._collect_recent_digest_document_ids(
        _PartiallyBrokenStore(), date(2026, 5, 14), lookback_days=2
    )
    assert result == ["doc_c"]


def test_run_pipeline_skips_when_digest_already_exists(monkeypatch):
    """락 획득 직후 같은 날짜 다이제스트가 이미 있으면 파이프라인을 다시 돌리지 않는다.

    부팅 startup 스레드가 막 생성을 끝낸 직후 scheduler loop 가 같은 날짜로 진입했을 때
    Solar Pro 호출이 두 번 일어나는 것을 방지하기 위한 가드의 동작을 검증합니다.
    """

    class _StoreWithExistingDigest:
        def get(self, digest_id):
            return object()  # truthy → "이미 있음"

    class _FakeSettings:
        digest_data_path = "/tmp/ignored"

    fetch_calls = {"count": 0}

    async def _should_not_fetch(target_date, sources=None):
        fetch_calls["count"] += 1
        return [], []

    monkeypatch.setattr(scheduled_pipeline, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(scheduled_pipeline, "FileDigestStore", lambda _path: _StoreWithExistingDigest())
    monkeypatch.setattr(scheduled_pipeline, "fetch_all_documents", _should_not_fetch)

    result = run_pipeline(date(2026, 5, 14), _config())

    assert result == "digest_20260514"
    assert fetch_calls["count"] == 0  # 수집 단계까지 진입하지 않아야 함


def test_run_pipeline_serializes_concurrent_calls(monkeypatch):
    """두 스레드가 동시에 run_pipeline 을 호출해도 직렬화되어 한 번에 하나만 실행된다."""
    import threading

    in_flight = {"count": 0, "max": 0}
    lock = threading.Lock()
    started = threading.Event()

    def _slow_locked_runner(run_date, config):
        with lock:
            in_flight["count"] += 1
            in_flight["max"] = max(in_flight["max"], in_flight["count"])
        started.set()
        # 두 스레드가 정말 직렬화되는지 확인하려면 두 번째 스레드가 락 대기 중인 상태에서
        # 첫 번째가 끝나야 한다. 짧은 sleep 으로 동시 진입 기회를 의도적으로 만든다.
        import time as _time
        _time.sleep(0.05)
        with lock:
            in_flight["count"] -= 1
        return f"digest_{run_date:%Y%m%d}"

    monkeypatch.setattr(scheduled_pipeline, "_run_pipeline_locked", _slow_locked_runner)

    results: list[str | None] = [None, None]

    def _call(idx: int):
        results[idx] = run_pipeline(date(2026, 5, 14), _config())

    t1 = threading.Thread(target=_call, args=(0,))
    t2 = threading.Thread(target=_call, args=(1,))
    t1.start()
    started.wait(timeout=1.0)
    t2.start()
    t1.join(timeout=2.0)
    t2.join(timeout=2.0)

    assert results == ["digest_20260514", "digest_20260514"]
    assert in_flight["max"] == 1  # 동시 진입 0 — 한 번에 하나만 실행


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
