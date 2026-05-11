"""Dashboard API for Streamlit integration."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.chroma_client import ChromaClient
from app.core.settings import Settings, get_settings

router = APIRouter()


class DashboardResponse(BaseModel):
    success: bool
    data: dict[str, Any] | None = None
    error: str | None = None


def get_chroma(settings: Settings = Depends(get_settings)) -> ChromaClient:
    return ChromaClient(settings)


@router.get("/dashboard", response_model=DashboardResponse)
def get_dashboard(chroma: ChromaClient = Depends(get_chroma)) -> DashboardResponse:
    try:
        document_count = chroma.count()
    except Exception as exc:
        return DashboardResponse(success=False, error=str(exc))

    return DashboardResponse(
        success=True,
        data={
            "latest_digest": None,
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
            "generated_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        },
    )
