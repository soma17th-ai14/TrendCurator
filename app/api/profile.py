"""사용자 프로필 API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.responses import ErrorResponse, error_response
from app.core.settings import Settings, get_settings
from app.services.profile_store import FileProfileStore, ProfileStoreError, UserProfile

router = APIRouter()


class ProfileResponse(BaseModel):
    success: bool
    data: dict[str, Any] | None = None
    error: ErrorResponse | None = None


class ProfileUpdateRequest(BaseModel):
    keywords: list[str] = Field(default_factory=lambda: ["LangGraph", "Multi-agent", "RAG"])
    language: str = "ko"
    digest_time: str = "09:00"


def get_profile_store(settings: Settings = Depends(get_settings)) -> FileProfileStore:
    return FileProfileStore(settings.profile_data_path)


@router.get("/profile", response_model=ProfileResponse)
def get_profile(
    store: FileProfileStore = Depends(get_profile_store),
) -> ProfileResponse:
    try:
        profile = store.load()
    except ProfileStoreError as exc:
        return ProfileResponse(
            success=False,
            error=error_response("PROFILE_NOT_FOUND", str(exc)),
        )

    if profile is None:
        return ProfileResponse(
            success=False,
            error=error_response("PROFILE_NOT_FOUND", "관심사 프로필이 설정되지 않았습니다."),
        )

    return ProfileResponse(success=True, data=profile.model_dump())


@router.put("/profile", response_model=ProfileResponse)
def update_profile(
    request: ProfileUpdateRequest,
    store: FileProfileStore = Depends(get_profile_store),
) -> ProfileResponse:
    try:
        store.save(UserProfile(
            keywords=request.keywords,
            language=request.language,
            digest_time=request.digest_time,
        ))
    except ProfileStoreError as exc:
        return ProfileResponse(
            success=False,
            error=error_response("PROFILE_NOT_FOUND", str(exc)),
        )

    return ProfileResponse(success=True, data={"message": "Profile updated"})
