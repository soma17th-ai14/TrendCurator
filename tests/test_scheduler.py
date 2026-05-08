from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.scheduler import (
    SchedulerConfig,
    SchedulerConfigError,
    SchedulerRunSkipped,
    SchedulerService,
    SchedulerState,
)


SEOUL = ZoneInfo("Asia/Seoul")


def test_scheduler_config_normalizes_time_and_sources() -> None:
    config = SchedulerConfig(time="9:00", sources=["huggingface", "hackernews"])

    assert config.time == "09:00"
    assert config.sources == ("huggingface", "hackernews")


def test_scheduler_config_rejects_invalid_time() -> None:
    with pytest.raises(SchedulerConfigError):
        SchedulerConfig(time="25:00")


def test_disabled_scheduler_does_not_run() -> None:
    service = SchedulerService(
        SchedulerState(config=SchedulerConfig(enabled=False, time="09:00"))
    )

    assert service.should_run(datetime(2026, 5, 6, 10, 0, tzinfo=SEOUL)) is False


def test_scheduler_does_not_run_before_scheduled_time() -> None:
    service = SchedulerService(SchedulerState(config=SchedulerConfig(time="09:00")))

    assert service.should_run(datetime(2026, 5, 6, 8, 59, tzinfo=SEOUL)) is False


def test_scheduler_runs_once_per_local_day() -> None:
    state = SchedulerState(
        config=SchedulerConfig(time="09:00"),
        last_run_at=datetime(2026, 5, 6, 9, 1, tzinfo=SEOUL),
    )
    service = SchedulerService(state)

    assert service.should_run(datetime(2026, 5, 6, 10, 0, tzinfo=SEOUL)) is False
    assert service.should_run(datetime(2026, 5, 7, 9, 0, tzinfo=SEOUL)) is True


def test_run_due_calls_runner_and_records_last_run_at() -> None:
    service = SchedulerService(SchedulerState(config=SchedulerConfig(time="09:00")))
    calls = []

    def runner(run_date, config):
        calls.append((run_date, config.sources))
        return "collect_20260506_001"

    result = service.run_due(runner, datetime(2026, 5, 6, 9, 0, tzinfo=SEOUL))

    assert calls == [
        (
            datetime(2026, 5, 6, tzinfo=SEOUL).date(),
            ("huggingface", "hackernews"),
        )
    ]
    assert result.ran is True
    assert result.job_id == "collect_20260506_001"
    assert result.last_run_at == datetime(2026, 5, 6, 9, 0, tzinfo=SEOUL)


def test_run_due_raises_when_scheduler_is_not_due() -> None:
    service = SchedulerService(SchedulerState(config=SchedulerConfig(time="09:00")))

    with pytest.raises(SchedulerRunSkipped):
        service.run_due(
            lambda run_date, config: None,
            datetime(2026, 5, 6, 8, 0, tzinfo=SEOUL),
        )

