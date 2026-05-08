from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import date, datetime, time
from typing import Callable, Mapping, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DEFAULT_SOURCES: tuple[str, ...] = ("huggingface", "hackernews")
SCHEDULER_ENABLED_ENV = "SCHEDULER_ENABLED"
SCHEDULER_TIME_ENV = "SCHEDULER_TIME"
SCHEDULER_TIMEZONE_ENV = "SCHEDULER_TIMEZONE"
SCHEDULER_SOURCES_ENV = "SCHEDULER_SOURCES"


class SchedulerConfigError(ValueError):
    """스케줄러 설정이 API 계약과 맞지 않을 때 발생합니다."""


class SchedulerRunSkipped(RuntimeError):
    """스케줄러 실행 시각이 되기 전에 실행을 요청했을 때 발생합니다."""


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
    def zoneinfo(self) -> ZoneInfo:
        return ZoneInfo(self.timezone)


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
        config = self._state.config
        if not config.enabled:
            return False

        local_now = self._local_now(now)
        if local_now.time() < config.scheduled_time:
            return False

        return self._last_run_date() != local_now.date()

    def run_due(
        self,
        runner: PipelineRunner,
        now: Optional[datetime] = None,
    ) -> SchedulerRunResult:
        if not self.should_run(now):
            raise SchedulerRunSkipped("scheduler is not due to run")

        local_now = self._local_now(now)
        run_date = local_now.date()
        job_id = runner(run_date, self._state.config)
        self._state = self._state.mark_run(local_now)

        return SchedulerRunResult(
            ran=True,
            run_date=run_date,
            last_run_at=self._state.last_run_at,
            job_id=job_id,
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


def validate_timezone(value: str) -> None:
    try:
        ZoneInfo(value)
    except ZoneInfoNotFoundError as exc:
        raise SchedulerConfigError(f"unknown timezone: {value}") from exc


def ensure_timezone(value: datetime, timezone: ZoneInfo) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone)
    return value.astimezone(timezone)


def load_scheduler_config_from_env(
    env: Optional[Mapping[str, str]] = None,
) -> SchedulerConfig:
    values = env or {}
    enabled = parse_bool_env(values.get(SCHEDULER_ENABLED_ENV), default=True)
    sources = parse_sources_env(values.get(SCHEDULER_SOURCES_ENV))

    return SchedulerConfig(
        enabled=enabled,
        time=values.get(SCHEDULER_TIME_ENV, "09:00"),
        timezone=values.get(SCHEDULER_TIMEZONE_ENV, "Asia/Seoul"),
        sources=sources,
    )


def parse_bool_env(value: Optional[str], default: bool) -> bool:
    if value is None or value.strip() == "":
        return default

    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False

    raise SchedulerConfigError(f"invalid boolean value: {value}")


def parse_sources_env(value: Optional[str]) -> tuple[str, ...]:
    if value is None or value.strip() == "":
        return DEFAULT_SOURCES

    sources = tuple(source.strip() for source in value.split(",") if source.strip())
    if not sources:
        raise SchedulerConfigError("sources must not be empty")
    return sources


def create_default_scheduler() -> SchedulerService:
    return SchedulerService(SchedulerState(config=SchedulerConfig()))


def create_scheduler_from_env(
    env: Optional[Mapping[str, str]] = None,
) -> SchedulerService:
    return SchedulerService(SchedulerState(config=load_scheduler_config_from_env(env)))
