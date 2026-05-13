"""run_startup_digest 부팅 자동 실행 함수 테스트."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

import pytest

from app.services import scheduled_pipeline
from app.services.scheduled_pipeline import PipelineRunError, run_startup_digest
from app.services.scheduler import SchedulerConfig


def _config() -> SchedulerConfig:
    return SchedulerConfig(enabled=True, time="09:00", timezone="UTC")


class _FakeDigestStore:
    def __init__(self, has_digest: bool) -> None:
        self._has_digest = has_digest

    def get(self, digest_id: str):
        return SimpleNamespace(digest_id=digest_id) if self._has_digest else None


def _patch_settings(monkeypatch, has_digest: bool):
    monkeypatch.setattr(
        scheduled_pipeline,
        "FileDigestStore",
        lambda path: _FakeDigestStore(has_digest=has_digest),
    )
    monkeypatch.setattr(
        scheduled_pipeline,
        "get_settings",
        lambda: SimpleNamespace(digest_data_path="ignored"),
    )


def test_skips_when_effective_date_digest_already_exists(monkeypatch):
    """효력 일자 다이제스트가 이미 있으면 run_pipeline을 호출하지 않는다."""
    _patch_settings(monkeypatch, has_digest=True)

    calls: list = []

    def _spy_run_pipeline(run_date, config):
        calls.append((run_date, config))
        return "should-not-run"

    monkeypatch.setattr(scheduled_pipeline, "run_pipeline", _spy_run_pipeline)
    monkeypatch.setattr(
        scheduled_pipeline,
        "effective_digest_date",
        lambda config, now=None: date(2026, 5, 14),
    )

    result = run_startup_digest(_config())

    assert result is None
    assert calls == []


def test_runs_pipeline_when_no_effective_date_digest(monkeypatch):
    """효력 일자 다이제스트가 없으면 run_pipeline을 호출하여 생성한다."""
    _patch_settings(monkeypatch, has_digest=False)

    calls: list = []

    def _spy_run_pipeline(run_date, config):
        calls.append((run_date, config))
        return "digest_20260514"

    monkeypatch.setattr(scheduled_pipeline, "run_pipeline", _spy_run_pipeline)
    monkeypatch.setattr(
        scheduled_pipeline,
        "effective_digest_date",
        lambda config, now=None: date(2026, 5, 14),
    )

    result = run_startup_digest(_config())

    assert result == "digest_20260514"
    assert len(calls) == 1
    assert calls[0][0] == date(2026, 5, 14)


def test_swallows_pipeline_run_error_and_returns_none(monkeypatch):
    """run_pipeline이 실패해도 부팅 흐름을 막지 않는다.

    Why: 부팅 자동 실행은 정상 스케줄 루프의 재시도와 분리돼 있어, 실패를 전파하면
    앱 lifespan 자체가 흔들릴 수 있다. 다음 스케줄 사이클에서 재시도되도록 None 반환만 한다.
    """
    _patch_settings(monkeypatch, has_digest=False)

    def _failing_run_pipeline(run_date, config):
        raise PipelineRunError("의도적 실패")

    monkeypatch.setattr(scheduled_pipeline, "run_pipeline", _failing_run_pipeline)
    monkeypatch.setattr(
        scheduled_pipeline,
        "effective_digest_date",
        lambda config, now=None: date(2026, 5, 14),
    )

    result = run_startup_digest(_config())

    assert result is None
