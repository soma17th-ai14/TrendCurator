"""Dashboard API for Streamlit integration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.responses import ErrorResponse, error_response
from app.api.scheduler import get_scheduler_service
from app.core.chroma_client import ChromaClient
from app.core.settings import Settings, get_settings
from app.services.collection_status_store import CollectionStatusStore
from app.services.digest_store import FileDigestStore
from app.services.scheduler import SchedulerConfig, SchedulerService, effective_digest_date

router = APIRouter()


class DashboardResponse(BaseModel):
    success: bool
    data: dict[str, Any] | None = None
    error: ErrorResponse | None = None


def get_chroma(settings: Settings = Depends(get_settings)) -> ChromaClient:
    return ChromaClient(settings)


def get_digest_store(settings: Settings = Depends(get_settings)) -> FileDigestStore:
    return FileDigestStore(settings.digest_data_path)


def get_collection_status_store(settings: Settings = Depends(get_settings)) -> CollectionStatusStore:
    return CollectionStatusStore(settings.collection_status_path)


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    chroma: ChromaClient = Depends(get_chroma),
    digest_store: FileDigestStore = Depends(get_digest_store),
    status_store: CollectionStatusStore = Depends(get_collection_status_store),
    scheduler: SchedulerService | None = Depends(get_scheduler_service),
) -> DashboardResponse:
    try:
        source_stats = chroma.count_by_source()
        top_tags = chroma.top_keywords(top_k=10)
        latest_digest = _latest_digest_data(digest_store)
        last_collected_at = status_store.load_collected_at()
        total_count = sum(source_stats.values())
        effective_date = _effective_date(scheduler)
        has_effective_digest = _has_digest_for_date(digest_store, effective_date)
    except Exception as exc:
        return DashboardResponse(
            success=False,
            error=error_response("DASHBOARD_UNAVAILABLE", str(exc)),
        )

    return DashboardResponse(
        success=True,
        data={
            "latest_digest": latest_digest,
            "effective_date": effective_date.isoformat(),
            "has_effective_digest": has_effective_digest,
            "collection_status": {
                "last_collected_at": last_collected_at,
                "collected_count": total_count,
                "filtered_count": total_count,
            },
            "source_stats": {
                "huggingface": source_stats.get("huggingface", 0),
                "hackernews": source_stats.get("hackernews", 0),
            },
            "top_tags": top_tags,
            "generated_at": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
        },
    )


def _latest_digest_data(store: FileDigestStore) -> dict[str, Any] | None:
    latest = store.latest()
    if latest is None:
        return None

    return {
        "digest_id": latest.digest_id,
        "date": latest.date.isoformat(),
        "item_count": latest.item_count,
    }


def _effective_date(scheduler: SchedulerService | None):
    """스케줄러가 초기화돼 있으면 그 설정의 효력 일자, 아니면 기본 설정 기준 효력 일자."""
    config = scheduler.state.config if scheduler is not None else SchedulerConfig()
    return effective_digest_date(config)


def _has_digest_for_date(store: FileDigestStore, target_date) -> bool:
    digest_id = f"digest_{target_date:%Y%m%d}"
    try:
        return store.get(digest_id) is not None
    except Exception:
        return False
