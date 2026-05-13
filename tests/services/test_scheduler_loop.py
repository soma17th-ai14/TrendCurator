"""SchedulerLoop 백그라운드 스레드 테스트."""

from __future__ import annotations

import threading
import time
from datetime import date, timedelta, timezone

from app.services.scheduler import SchedulerConfig, SchedulerService, SchedulerState
from app.services.scheduler_loop import SchedulerLoop

SEOUL = timezone(timedelta(hours=9), name="Asia/Seoul")


def _past_time_config() -> SchedulerConfig:
    """스케줄 시각이 이미 지나 run_due가 즉시 실행되는 설정을 반환합니다."""
    return SchedulerConfig(enabled=True, time="00:01", timezone="UTC")


def _disabled_config() -> SchedulerConfig:
    """비활성화 상태라 항상 건너뛰는 설정을 반환합니다."""
    return SchedulerConfig(enabled=False, time="09:00", timezone="UTC")


def test_scheduler_loop_calls_runner_when_due():
    called: list[tuple[date, SchedulerConfig]] = []

    def fake_runner(run_date: date, config: SchedulerConfig) -> str | None:
        called.append((run_date, config))
        return "job-001"

    config = _past_time_config()
    service = SchedulerService(SchedulerState(config=config))
    loop = SchedulerLoop(service, runner=fake_runner)
    loop.start()
    time.sleep(0.3)
    loop.stop()

    assert len(called) == 1
    run_date, used_config = called[0]
    assert isinstance(run_date, date)
    assert used_config.enabled is True


def test_scheduler_loop_skips_when_not_due():
    called: list = []

    def fake_runner(run_date: date, config: SchedulerConfig) -> str | None:
        called.append(run_date)
        return None

    config = _disabled_config()
    service = SchedulerService(SchedulerState(config=config))
    loop = SchedulerLoop(service, runner=fake_runner)
    loop.start()
    time.sleep(0.3)
    loop.stop()

    assert called == []


def test_scheduler_loop_stop_terminates_thread():
    config = _disabled_config()
    service = SchedulerService(SchedulerState(config=config))
    loop = SchedulerLoop(service, runner=lambda d, c: None)
    loop.start()

    assert loop._thread is not None
    assert loop._thread.is_alive()

    loop.stop()
    assert not loop._thread.is_alive()


def test_scheduler_loop_runner_error_does_not_crash_loop():
    def failing_runner(run_date: date, config: SchedulerConfig) -> str | None:
        raise RuntimeError("의도적 실패")

    config = _past_time_config()
    service = SchedulerService(SchedulerState(config=config))
    loop = SchedulerLoop(service, runner=failing_runner)
    loop.start()
    assert loop._thread is not None
    assert loop._thread.is_alive()  # stop() 전에 살아있는지 확인
    loop.stop()
