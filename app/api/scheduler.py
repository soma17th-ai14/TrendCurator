"""정기 발행 스케줄러 API."""

from __future__ import annotations

import threading
from datetime import datetime
from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, ValidationError

from app.api.responses import ErrorResponse, error_response
from app.core.models import Source
from app.core.scheduler_settings import create_scheduler_from_env
from app.services.scheduler import SchedulerConfig, SchedulerConfigError, SchedulerService, SchedulerState

if TYPE_CHECKING:
    from app.services.scheduler_loop import SchedulerLoop

router = APIRouter()

_SCHEDULER: SchedulerService | None = None
_SCHEDULER_ERROR: str | None = None
_LOOP: SchedulerLoop | None = None
_LOOP_LOCK = threading.Lock()


def ensure_loop_running(scheduler: SchedulerService) -> None:
    """루프가 실행 중이 아니면 시작합니다. 이미 살아있으면 무시합니다.

    동시 호출 시 중복 스레드가 생성되지 않도록 모듈 단위 lock으로 check-then-start를
    원자적으로 수행합니다.
    """
    global _LOOP
    with _LOOP_LOCK:
        if _LOOP is not None and _LOOP._thread is not None and _LOOP._thread.is_alive():
            return
        from app.services.scheduler_loop import SchedulerLoop
        _LOOP = SchedulerLoop(scheduler)
        _LOOP.start()


def stop_scheduler_loop() -> None:
    """실행 중인 루프를 중단합니다."""
    global _LOOP
    with _LOOP_LOCK:
        if _LOOP is not None:
            _LOOP.stop()
            _LOOP = None


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


def get_scheduler_service() -> SchedulerService | None:
    global _SCHEDULER, _SCHEDULER_ERROR
    if _SCHEDULER is None and _SCHEDULER_ERROR is None:
        try:
            _SCHEDULER = create_scheduler_from_env()
        except SchedulerConfigError as exc:
            _SCHEDULER_ERROR = str(exc)
    return _SCHEDULER


def _init_error_response() -> SchedulerResponse:
    return SchedulerResponse(
        success=False,
        error=error_response("SCHEDULER_ERROR", _SCHEDULER_ERROR or "스케줄러를 초기화할 수 없습니다."),
    )


@router.get("/scheduler", response_model=SchedulerResponse)
def get_scheduler(
    scheduler: SchedulerService | None = Depends(get_scheduler_service),
) -> SchedulerResponse:
    if scheduler is None:
        return _init_error_response()
    try:
        data = _scheduler_data(scheduler)
    except (SchedulerConfigError, ValidationError) as exc:
        return SchedulerResponse(
            success=False,
            error=error_response("SCHEDULER_ERROR", str(exc)),
        )

    return SchedulerResponse(success=True, data=data)


@router.put("/scheduler", response_model=SchedulerResponse)
def update_scheduler(
    request: SchedulerUpdateRequest,
    scheduler: SchedulerService | None = Depends(get_scheduler_service),
) -> SchedulerResponse:
    global _SCHEDULER, _SCHEDULER_ERROR
    try:
        config = SchedulerConfig(
            enabled=request.enabled,
            time=request.time,
            timezone=request.timezone,
            sources=tuple(request.sources),
        )
        if scheduler is None:
            _SCHEDULER = SchedulerService(SchedulerState(config=config))
            _SCHEDULER_ERROR = None
            scheduler = _SCHEDULER
        else:
            scheduler.update_config(config)
        ensure_loop_running(scheduler)
    except SchedulerConfigError as exc:
        return SchedulerResponse(
            success=False,
            error=error_response("SCHEDULER_ERROR", str(exc)),
        )

    try:
        data = _scheduler_data(scheduler)
    except (SchedulerConfigError, ValidationError) as exc:
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
