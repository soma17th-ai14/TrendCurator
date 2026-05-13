"""TrendCurator FastAPI 앱 진입점."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.dashboard import router as dashboard_router
from app.api.digest import router as digest_router
from app.api.documents import router as documents_router
from app.api.groundedness import router as groundedness_router
from app.api.pipeline import router as pipeline_router
from app.api.query import router as query_router
from app.api.profile import router as profile_router
from app.api.scheduler import router as scheduler_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # SCHEDULER_AUTOSTART=1 환경변수가 있을 때만 시작 시 루프를 자동 시작합니다.
    # 테스트 환경에서는 이 변수를 설정하지 않으면 루프가 시작되지 않습니다.
    if os.getenv("SCHEDULER_AUTOSTART", "").lower() in ("1", "true", "yes"):
        from app.api.scheduler import ensure_loop_running, get_scheduler_service
        scheduler = get_scheduler_service()
        if scheduler is not None:
            ensure_loop_running(scheduler)
    try:
        yield
    finally:
        from app.api.scheduler import stop_scheduler_loop
        stop_scheduler_loop()


app = FastAPI(title="TrendCurator API", lifespan=lifespan)
API_PREFIX = "/api/v1"

app.include_router(pipeline_router, prefix=API_PREFIX)
app.include_router(documents_router, prefix=API_PREFIX)
app.include_router(groundedness_router, prefix=API_PREFIX)
app.include_router(query_router, prefix=API_PREFIX)
app.include_router(dashboard_router, prefix=API_PREFIX)
app.include_router(digest_router, prefix=API_PREFIX)
app.include_router(scheduler_router, prefix=API_PREFIX)
app.include_router(profile_router, prefix=API_PREFIX)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
