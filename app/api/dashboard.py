"""Dashboard API for Streamlit integration."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.responses import ErrorResponse, error_response
from app.core.chroma_client import ChromaClient
from app.core.settings import Settings, get_settings
from app.services.digest_store import FileDigestStore

router = APIRouter()


class DashboardResponse(BaseModel):
    success: bool
    data: dict[str, Any] | None = None
    error: ErrorResponse | None = None


def get_chroma(settings: Settings = Depends(get_settings)) -> ChromaClient:
    return ChromaClient(settings)


def get_digest_store(settings: Settings = Depends(get_settings)) -> FileDigestStore:
    return FileDigestStore(settings.digest_data_path)


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(
    chroma: ChromaClient = Depends(get_chroma),
    digest_store: FileDigestStore = Depends(get_digest_store),
) -> DashboardResponse:
    try:
        document_count = chroma.count()
        latest_digest = _latest_digest_data(digest_store)
    except Exception as exc:
        return DashboardResponse(
            success=False,
            error=error_response("DASHBOARD_UNAVAILABLE", str(exc)),
        )

    return DashboardResponse(
        success=True,
        data={
            "latest_digest": latest_digest,
            "collection_status": {
                "last_collected_at": None,
                "collected_count": document_count,
                "filtered_count": document_count,
            },
            "source_stats": {
                "huggingface": None,
                "hackernews": None,
            },
            "top_tags": [],
            "generated_at": datetime.now(timezone.utc)
            .isoformat(timespec="seconds")
            .replace("+00:00", "Z"),
        },
    )


def _latest_digest_data(store: FileDigestStore) -> dict[str, Any] | None:
    latest = next(iter(store.list()), None)
    if latest is None:
        return None

    return {
        "digest_id": latest.digest_id,
        "date": latest.date.isoformat(),
        "item_count": latest.item_count,
    }
