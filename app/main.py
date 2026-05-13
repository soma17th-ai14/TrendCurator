"""TrendCurator FastAPI 앱 진입점."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.dashboard import router as dashboard_router
from app.api.digest import router as digest_router
from app.api.documents import router as documents_router
from app.api.groundedness import router as groundedness_router
from app.api.pipeline import router as pipeline_router
from app.api.query import router as query_router
from app.api.profile import router as profile_router
from app.api.scheduler import get_scheduler_service
from app.api.scheduler import router as scheduler_router
from app.services.scheduler_loop import SchedulerLoop


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = get_scheduler_service()
    loop = None
    if scheduler is not None:
        loop = SchedulerLoop(scheduler)
        loop.start()
    try:
        yield
    finally:
        if loop is not None:
            loop.stop()


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
