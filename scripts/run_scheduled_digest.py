from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from app.core.scheduler_settings import create_scheduler_from_env
from app.services.scheduler import SchedulerConfig, SchedulerService


EXIT_SUCCESS = 0
EXIT_NOT_IMPLEMENTED = 2


def run_daily_digest_pipeline(run_date: date, config: SchedulerConfig) -> Optional[str]:
    """정기 Daily Digest 파이프라인을 실행합니다."""
    raise NotImplementedError(
        "Daily Digest 파이프라인이 구현되면 이 함수에서 실제 발행 서비스를 호출합니다."
    )


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
