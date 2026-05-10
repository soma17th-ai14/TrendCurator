from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from typing import Callable, Literal, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_SOURCES: tuple[str, ...] = ("huggingface", "hackernews")


class SchedulerConfigError(ValueError):
    """스케줄러 설정이 API 계약과 맞지 않을 때 발생합니다."""


SchedulerSkippedReason = Literal["disabled", "before_scheduled_time", "already_ran_today"]


@dataclass(frozen=True)
class SchedulerConfig:
    enabled: bool = True
    time: str = "09:00"
    timezone: str = "Asia/Seoul"
    sources: tuple[str, ...] = DEFAULT_SOURCES

    def __post_init__(self) -> None:
        scheduled_time = parse_schedule_time(self.time)
        validate_timezone(self.timezone)

        if not self.sources:
            raise SchedulerConfigError("sources must not be empty")

        normalized_sources = tuple(self.sources)
        object.__setattr__(self, "time", scheduled_time.strftime("%H:%M"))
        object.__setattr__(self, "sources", normalized_sources)

    @property
    def scheduled_time(self) -> time:
        return parse_schedule_time(self.time)

    @property
    def zoneinfo(self) -> tzinfo:
        return get_timezone(self.timezone)


@dataclass(frozen=True)
class SchedulerState:
    config: SchedulerConfig
    last_run_at: Optional[datetime] = None

    def with_config(self, config: SchedulerConfig) -> SchedulerState:
        return replace(self, config=config)

    def mark_run(self, run_at: datetime) -> SchedulerState:
        return replace(self, last_run_at=ensure_timezone(run_at, self.config.zoneinfo))


@dataclass(frozen=True)
class SchedulerRunResult:
    ran: bool
    run_date: Optional[date]
    last_run_at: Optional[datetime]
    job_id: Optional[str] = None
    skipped_reason: Optional[SchedulerSkippedReason] = None


PipelineRunner = Callable[[date, SchedulerConfig], Optional[str]]


class SchedulerService:
    def __init__(self, state: SchedulerState) -> None:
        self._state = state

    @property
    def state(self) -> SchedulerState:
        return self._state

    def update_config(self, config: SchedulerConfig) -> SchedulerState:
        self._state = self._state.with_config(config)
        return self._state

    def should_run(self, now: Optional[datetime] = None) -> bool:
        return self.skip_reason(now) is None

    def skip_reason(self, now: Optional[datetime] = None) -> Optional[SchedulerSkippedReason]:
        config = self._state.config
        if not config.enabled:
            return "disabled"

        local_now = self._local_now(now)
        if local_now.time() < config.scheduled_time:
            return "before_scheduled_time"

        if self._last_run_date() == local_now.date():
            return "already_ran_today"

        return None

    def run_due(
        self,
        runner: PipelineRunner,
        now: Optional[datetime] = None,
    ) -> SchedulerRunResult:
        local_now = self._local_now(now)
        skipped_reason = self.skip_reason(local_now)
        if skipped_reason is not None:
            return SchedulerRunResult(
                ran=False,
                run_date=None,
                last_run_at=self._state.last_run_at,
                job_id=None,
                skipped_reason=skipped_reason,
            )

        run_date = local_now.date()
        job_id = runner(run_date, self._state.config)
        self._state = self._state.mark_run(local_now)

        return SchedulerRunResult(
            ran=True,
            run_date=run_date,
            last_run_at=self._state.last_run_at,
            job_id=job_id,
            skipped_reason=None,
        )

    def next_run_at(self, now: Optional[datetime] = None) -> datetime:
        config = self._state.config
        local_now = self._local_now(now)
        candidate = datetime.combine(
            local_now.date(),
            config.scheduled_time,
            tzinfo=config.zoneinfo,
        )

        if local_now < candidate and self._last_run_date() != candidate.date():
            return candidate

        next_day = local_now.date().toordinal() + 1
        return datetime.combine(
            date.fromordinal(next_day),
            config.scheduled_time,
            tzinfo=config.zoneinfo,
        )

    def _local_now(self, now: Optional[datetime]) -> datetime:
        current = now or datetime.now(tz=self._state.config.zoneinfo)
        return ensure_timezone(current, self._state.config.zoneinfo)

    def _last_run_date(self) -> Optional[date]:
        if self._state.last_run_at is None:
            return None
        return ensure_timezone(self._state.last_run_at, self._state.config.zoneinfo).date()


def parse_schedule_time(value: str) -> time:
    try:
        parsed = datetime.strptime(value, "%H:%M").time()
    except ValueError as exc:
        raise SchedulerConfigError("time must be HH:MM") from exc

    return parsed.replace(second=0, microsecond=0)


def get_timezone(value: str) -> tzinfo:
    try:
        return ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        if value == "UTC":
            return timezone.utc
        if value == "Asia/Seoul":
            return timezone(timedelta(hours=9), name="Asia/Seoul")
        raise SchedulerConfigError(f"unknown timezone: {value}") from exc


def validate_timezone(value: str) -> None:
    get_timezone(value)


def ensure_timezone(value: datetime, timezone: tzinfo) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone)
    return value.astimezone(timezone)


def create_default_scheduler() -> SchedulerService:
    return SchedulerService(SchedulerState(config=SchedulerConfig()))
