from __future__ import annotations

import os
from typing import Mapping, Optional

from app.services.scheduler import (
    DEFAULT_SOURCES,
    SchedulerConfig,
    SchedulerConfigError,
    SchedulerService,
    SchedulerState,
)


SCHEDULER_ENABLED_ENV = "SCHEDULER_ENABLED"
SCHEDULER_TIME_ENV = "SCHEDULER_TIME"
SCHEDULER_TIMEZONE_ENV = "SCHEDULER_TIMEZONE"
SCHEDULER_SOURCES_ENV = "SCHEDULER_SOURCES"


def load_scheduler_config_from_env(
    env: Optional[Mapping[str, str]] = None,
) -> SchedulerConfig:
    """환경변수에서 스케줄러 설정을 읽어옵니다."""
    values = os.environ if env is None else env
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


def create_scheduler_from_env(
    env: Optional[Mapping[str, str]] = None,
) -> SchedulerService:
    config = load_scheduler_config_from_env(env)
    return SchedulerService(SchedulerState(config=config))
