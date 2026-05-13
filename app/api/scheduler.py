"""정기 발행 스케줄러 API."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.responses import ErrorResponse, error_response
from app.core.models import Source
from app.core.scheduler_settings import create_scheduler_from_env
from app.services.scheduler import SchedulerConfig, SchedulerConfigError, SchedulerService

router = APIRouter()

_SCHEDULER: SchedulerService | None = None


class SchedulerData(BaseModel):
    enabled: bool
    time: str
    timezone: str
    sources: list[Source]
    last_run_at: str | None
    next_run_at: str


class SchedulerResponse(BaseModel):
    success: bool
    data: SchedulerData | None = None
    error: ErrorResponse | None = None


class SchedulerUpdateRequest(BaseModel):
    enabled: bool = True
    time: str = "09:00"
    timezone: str = "Asia/Seoul"
    sources: list[Source] = Field(default_factory=lambda: ["huggingface", "hackernews"])


def get_scheduler_service() -> SchedulerService:
    global _SCHEDULER
    if _SCHEDULER is None:
        _SCHEDULER = create_scheduler_from_env()
    return _SCHEDULER


@router.get("/scheduler", response_model=SchedulerResponse)
def get_scheduler(
    scheduler: SchedulerService = Depends(get_scheduler_service),
) -> SchedulerResponse:
    try:
        data = _scheduler_data(scheduler)
    except SchedulerConfigError as exc:
        return SchedulerResponse(
            success=False,
            error=error_response("SCHEDULER_ERROR", str(exc)),
        )

    return SchedulerResponse(success=True, data=data)


@router.put("/scheduler", response_model=SchedulerResponse)
def update_scheduler(
    request: SchedulerUpdateRequest,
    scheduler: SchedulerService = Depends(get_scheduler_service),
) -> SchedulerResponse:
    try:
        config = SchedulerConfig(
            enabled=request.enabled,
            time=request.time,
            timezone=request.timezone,
            sources=tuple(request.sources),
        )
        scheduler.update_config(config)
    except SchedulerConfigError as exc:
        return SchedulerResponse(
            success=False,
            error=error_response("SCHEDULER_ERROR", str(exc)),
        )

    try:
        data = _scheduler_data(scheduler)
    except SchedulerConfigError as exc:
        return SchedulerResponse(
            success=False,
            error=error_response("SCHEDULER_ERROR", str(exc)),
        )

    return SchedulerResponse(success=True, data=data)


def _scheduler_data(scheduler: SchedulerService) -> SchedulerData:
    state = scheduler.state
    config = state.config
    last_run_at = _datetime_or_none(state.last_run_at)
    return SchedulerData(
        enabled=config.enabled,
        time=config.time,
        timezone=config.timezone,
        sources=list(config.sources),
        last_run_at=last_run_at,
        next_run_at=scheduler.next_run_at(datetime.now(tz=config.zoneinfo)).isoformat(),
    )


def _datetime_or_none(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()
