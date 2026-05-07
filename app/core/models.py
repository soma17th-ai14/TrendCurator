"""Shared data contracts based on docs/api-spec.md."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

SourceName = Literal["huggingface", "hackernews"]
DocumentCategory = Literal["agent", "rag", "llm", "framework", "benchmark"]


@dataclass(frozen=True)
class Document:
    """API-facing document contract used by pipeline and digest modules."""

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
class DigestItem:
    """Daily Digest item contract from docs/api-spec.md."""

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
    """Document selected for digest generation with retrieval metadata."""

    document: Document
    relevance_score: float
    matched_keywords: list[str]


@dataclass(frozen=True)
class SchedulerConfig:
    """Scheduler settings exposed by GET/PUT /scheduler."""

    enabled: bool
    time: str
    timezone: str = "Asia/Seoul"
    sources: list[SourceName] = field(default_factory=lambda: ["huggingface", "hackernews"])
    last_run_at: str | None = None


def parse_iso_datetime(value: str) -> datetime:
    """Parse an ISO datetime string accepted by the API documents."""

    return datetime.fromisoformat(value)
