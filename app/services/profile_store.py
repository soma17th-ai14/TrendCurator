"""사용자 프로필 저장소.

관심사 키워드, 언어, Digest 발행 시각을 파일 기반 JSON으로 영속화한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import NamedTemporaryFile

from pydantic import BaseModel, Field


class UserProfile(BaseModel):
    keywords: list[str] = Field(default_factory=lambda: ["LangGraph", "Multi-agent", "RAG"])
    language: str = "ko"
    digest_time: str = "09:00"


class ProfileStoreError(RuntimeError):
    """프로필 저장소를 읽거나 쓸 수 없을 때 발생합니다."""


class FileProfileStore:
    """UserProfile을 단일 JSON 파일로 저장합니다."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def load(self) -> UserProfile | None:
        if not self._path.exists():
            return None
        try:
            payload = json.loads(self._path.read_text(encoding="utf-8"))
            return UserProfile(**payload)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            raise ProfileStoreError("프로필 조회 실패") from exc

    def save(self, profile: UserProfile) -> UserProfile:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=self._path.parent,
                delete=False,
                suffix=".tmp",
            ) as temp_file:
                json.dump(profile.model_dump(), temp_file, ensure_ascii=False, indent=2)
                temp_file.write("\n")
                temp_path = Path(temp_file.name)
            temp_path.replace(self._path)
        except OSError as exc:
            raise ProfileStoreError("프로필 저장 실패") from exc
        return profile
