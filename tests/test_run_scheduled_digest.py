from datetime import datetime, timedelta, timezone

import scripts.run_scheduled_digest as entrypoint
from app.services.scheduler import SchedulerConfig, SchedulerService, SchedulerState


SEOUL = timezone(timedelta(hours=9), name="Asia/Seoul")


def test_run_once_skips_before_scheduled_time(capsys) -> None:
    scheduler = SchedulerService(SchedulerState(config=SchedulerConfig(time="09:00")))

    exit_code = entrypoint.run_once(
        scheduler,
        datetime(2026, 5, 6, 8, 0, tzinfo=SEOUL),
    )

    assert exit_code == entrypoint.EXIT_SUCCESS
    output = capsys.readouterr().out
    assert "스케줄 실행 대상이 아닙니다." in output
    assert "reason=before_scheduled_time" in output


def test_run_once_reports_missing_pipeline_when_due(capsys) -> None:
    scheduler = SchedulerService(SchedulerState(config=SchedulerConfig(time="09:00")))

    exit_code = entrypoint.run_once(
        scheduler,
        datetime(2026, 5, 6, 9, 0, tzinfo=SEOUL),
    )

    assert exit_code == entrypoint.EXIT_NOT_IMPLEMENTED
    assert "Daily Digest 파이프라인이 구현되면" in capsys.readouterr().out


def test_run_once_executes_configured_pipeline(monkeypatch, capsys) -> None:
    scheduler = SchedulerService(SchedulerState(config=SchedulerConfig(time="09:00")))
    calls = []

    def fake_pipeline(run_date, config):
        calls.append((run_date, config.sources))
        return "digest_20260506"

    monkeypatch.setattr(entrypoint, "run_daily_digest_pipeline", fake_pipeline)

    exit_code = entrypoint.run_once(
        scheduler,
        datetime(2026, 5, 6, 9, 0, tzinfo=SEOUL),
    )

    assert exit_code == entrypoint.EXIT_SUCCESS
    assert calls == [
        (
            datetime(2026, 5, 6, tzinfo=SEOUL).date(),
            ("huggingface", "hackernews"),
        )
    ]
    assert "스케줄 실행 완료" in capsys.readouterr().out
