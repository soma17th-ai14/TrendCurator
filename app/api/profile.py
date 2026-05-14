"""사용자 프로필 API."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.api.responses import ErrorResponse, error_response
from app.api.scheduler import get_scheduler_service
from app.core.settings import Settings, get_settings
from app.services.profile_store import FileProfileStore, ProfileStoreError, UserProfile
from app.services.scheduler import SchedulerConfig, SchedulerConfigError, SchedulerService

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
    scheduler: SchedulerService | None = Depends(get_scheduler_service),
) -> ProfileResponse:
    # 기존 키워드와의 차이를 감지해, 변경 시 사용자에게 재생성 안내를 돌려줍니다.
    # 새 키워드는 다음 스케줄 사이클 또는 수동 재생성 때만 다이제스트에 반영되기 때문입니다.
    previous_keywords: list[str] = []
    try:
        existing = store.load()
        if existing is not None:
            previous_keywords = list(existing.keywords)
    except ProfileStoreError:
        previous_keywords = []

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

    if scheduler is not None:
        try:
            current = scheduler.state.config
            scheduler.update_config(SchedulerConfig(
                enabled=current.enabled,
                time=request.digest_time,
                timezone=current.timezone,
                sources=current.sources,
            ))
        except SchedulerConfigError:
            pass

    keywords_changed = previous_keywords != list(request.keywords)
    if keywords_changed:
        message = (
            "프로필이 저장되었습니다. 키워드가 변경되었으므로, 새 키워드를 반영하려면 "
            "오늘의 Digest 재생성 버튼을 눌러주세요. 기존 다이제스트는 자동으로 갱신되지 않습니다."
        )
    else:
        message = "프로필이 저장되었습니다."

    return ProfileResponse(
        success=True,
        data={"message": message, "keywords_changed": keywords_changed},
    )
