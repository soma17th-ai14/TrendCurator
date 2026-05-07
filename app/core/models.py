"""docs/api-spec.md를 기준으로 한 공통 데이터 계약."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

SourceName = Literal["huggingface", "hackernews"]
DocumentCategory = Literal["agent", "rag", "llm", "framework", "benchmark"]


@dataclass(frozen=True)
class Document:
    """파이프라인과 Digest 모듈에서 공유하는 API 문서 계약입니다."""

    document_id: str
    title: str
    source: SourceName
    url: str
    published_at: str
    collected_at: str
    category: DocumentCategory
    tags: list[str]
    content: str
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def searchable_text(self) -> str:
        return " ".join(
            part
            for part in [
                self.title,
                self.summary,
                self.content,
                " ".join(self.tags),
                self.category,
            ]
            if part
        )


@dataclass(frozen=True)
class NormalizedDocument:
    """Normalizer가 Chunker로 넘기는 내부 문서 계약입니다.

    외부 API 응답용 `Document`와 달리, 원문 추적과 중복 제거에 필요한
    `external_id`, `content_hash`, `raw_text`를 유지합니다.
    """

    doc_id: str
    source: SourceName
    title: str
    url: str
    published_date: str
    raw_text: str
    category_hint: str
    external_id: str
    content_hash: str
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def searchable_text(self) -> str:
        metadata_terms = []
        authors = self.metadata.get("authors")
        if isinstance(authors, list):
            metadata_terms.extend(str(author) for author in authors)

        return " ".join(
            part
            for part in [
                self.title,
                self.raw_text,
                self.category_hint,
                " ".join(metadata_terms),
            ]
            if part
        )


@dataclass(frozen=True)
class DigestItem:
    """docs/api-spec.md의 Daily Digest 항목 계약입니다."""

    title: str
    source: SourceName
    url: str
    summary: str
    key_points: list[str]
    contribution: str
    benchmark: str
    critique: str
    tags: list[str]


@dataclass(frozen=True)
class DigestCandidate:
    """Digest 생성 후보 문서와 검색/필터링 메타데이터입니다."""

    document: Document
    relevance_score: float
    matched_keywords: list[str]


@dataclass(frozen=True)
class SchedulerConfig:
    """GET/PUT /scheduler에서 노출할 스케줄러 설정입니다."""

    enabled: bool
    time: str
    timezone: str = "Asia/Seoul"
    sources: list[SourceName] = field(default_factory=lambda: ["huggingface", "hackernews"])
    last_run_at: str | None = None


def parse_iso_datetime(value: str) -> datetime:
    """API 문서에서 사용하는 ISO datetime 문자열을 파싱합니다."""

    return datetime.fromisoformat(value)
