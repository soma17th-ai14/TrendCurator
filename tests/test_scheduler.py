from datetime import datetime, timedelta, timezone

import pytest

from app.services.scheduler import (
    SchedulerConfig,
    SchedulerConfigError,
    SchedulerService,
    SchedulerState,
)


SEOUL = timezone(timedelta(hours=9), name="Asia/Seoul")


def test_scheduler_config_normalizes_time_and_sources() -> None:
    config = SchedulerConfig(time="9:00", sources=["huggingface", "hackernews"])

    assert config.time == "09:00"
    assert config.sources == ("huggingface", "hackernews")


def test_scheduler_config_rejects_invalid_time() -> None:
    with pytest.raises(SchedulerConfigError):
        SchedulerConfig(time="25:00")


def test_disabled_scheduler_returns_skipped_result() -> None:
    service = SchedulerService(
        SchedulerState(config=SchedulerConfig(enabled=False, time="09:00"))
    )
    calls = []

    result = service.run_due(
        lambda run_date, config: calls.append((run_date, config)),
        datetime(2026, 5, 6, 10, 0, tzinfo=SEOUL),
    )

    assert result.ran is False
    assert result.run_date is None
    assert result.job_id is None
    assert result.skipped_reason == "disabled"
    assert calls == []


def test_scheduler_returns_before_scheduled_time_reason() -> None:
    service = SchedulerService(SchedulerState(config=SchedulerConfig(time="09:00")))

    result = service.run_due(
        lambda run_date, config: "digest_20260506",
        datetime(2026, 5, 6, 8, 59, tzinfo=SEOUL),
    )

    assert service.should_run(datetime(2026, 5, 6, 8, 59, tzinfo=SEOUL)) is False
    assert result.ran is False
    assert result.skipped_reason == "before_scheduled_time"


def test_scheduler_runs_once_per_local_day() -> None:
    state = SchedulerState(
        config=SchedulerConfig(time="09:00"),
        last_run_at=datetime(2026, 5, 6, 9, 1, tzinfo=SEOUL),
    )
    service = SchedulerService(state)

    result = service.run_due(
        lambda run_date, config: "digest_20260506",
        datetime(2026, 5, 6, 10, 0, tzinfo=SEOUL),
    )

    assert result.ran is False
    assert result.skipped_reason == "already_ran_today"
    assert service.should_run(datetime(2026, 5, 7, 9, 0, tzinfo=SEOUL)) is True


def test_run_due_calls_runner_and_records_digest_job_id() -> None:
    service = SchedulerService(SchedulerState(config=SchedulerConfig(time="09:00")))
    calls = []

    def runner(run_date, config):
        calls.append((run_date, config.sources))
        return "digest_20260506"

    result = service.run_due(runner, datetime(2026, 5, 6, 9, 0, tzinfo=SEOUL))

    assert calls == [
        (
            datetime(2026, 5, 6, tzinfo=SEOUL).date(),
            ("huggingface", "hackernews"),
        )
    ]
    assert result.ran is True
    assert result.run_date == datetime(2026, 5, 6, tzinfo=SEOUL).date()
    assert result.job_id == "digest_20260506"
    assert result.skipped_reason is None
    assert result.last_run_at == datetime(2026, 5, 6, 9, 0, tzinfo=SEOUL)
