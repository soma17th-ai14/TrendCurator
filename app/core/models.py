"""공통 데이터 모델.

api-spec.md 11장 Document 모델을 Pydantic v2로 구현한다.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

Source = Literal["huggingface", "hackernews"]
Category = Literal["agent", "rag", "llm", "framework", "benchmark"]


class Document(BaseModel):
    document_id: str
    title: str
    source: Source
    url: str
    published_at: date | None = None
    collected_at: datetime
    category: Category
    tags: list[str] = Field(default_factory=list)
    content: str
    summary: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DigestCandidate(BaseModel):
    document_id: str
    source: Source
    title: str
    url: str
    published_at: date | None = None
    content: str
    summary_preview: str
    similarity_score: float = Field(ge=0.0, le=1.0)
    relevance_score: float = Field(ge=0.0, le=1.0)
    matched_keywords: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DailyDigestRetrievalRequest(BaseModel):
    digest_date: date
    lookback_days: int = Field(default=1, ge=1)
    top_k: int = Field(default=10, ge=1)
    profile_based: bool = True
    keywords: list[str] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    min_relevance_score: float = Field(default=0.18, ge=0.0, le=1.0)


class DailyDigestRetrievalResult(BaseModel):
    digest_date: date
    candidates: list[DigestCandidate] = Field(default_factory=list)
    total_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)

    @model_validator(mode="after")
    def selected_count_cannot_exceed_candidates(self) -> "DailyDigestRetrievalResult":
        if self.total_count < len(self.candidates):
            raise ValueError("total_count cannot be less than candidates length")
        if self.selected_count > len(self.candidates):
            raise ValueError("selected_count cannot exceed candidates length")
        if self.selected_count > self.total_count:
            raise ValueError("selected_count cannot exceed total_count")
        return self


class DigestItem(BaseModel):
    document_id: str
    title: str
    source: Source
    url: str
    published_at: date | None = None
    summary: str
    key_points: list[str] = Field(default_factory=list)
    contribution: str
    benchmark: str
    critique: str
    tags: list[str] = Field(default_factory=list)
    evidence_document_ids: list[str] = Field(default_factory=list)
    llm_model: str = "solar-pro-3"


class SolarProDigestGenerationRequest(BaseModel):
    digest_date: date
    language: str = "ko"
    profile_keywords: list[str] = Field(default_factory=list)
    candidates: list[DigestCandidate] = Field(default_factory=list)


class SolarProDigestGenerationResult(BaseModel):
    digest_id: str
    date: date
    title: str
    items: list[DigestItem] = Field(default_factory=list)
    groundedness_score: float = Field(ge=0.0, le=1.0)


class DigestGenerationRunResult(BaseModel):
    digest_id: str
    date: date
    status: Literal["completed"] = "completed"
    item_count: int = Field(ge=0)
    candidate_count: int = Field(ge=0)
    selected_candidate_count: int = Field(ge=0)
    source_document_ids: list[str] = Field(default_factory=list)
    groundedness_score: float = Field(ge=0.0, le=1.0)
    digest: SolarProDigestGenerationResult

    @model_validator(mode="after")
    def counts_match_digest(self) -> "DigestGenerationRunResult":
        if self.item_count != len(self.digest.items):
            raise ValueError("item_count must match digest items length")
        if self.selected_candidate_count > self.candidate_count:
            raise ValueError("selected_candidate_count cannot exceed candidate_count")
        if self.item_count > self.selected_candidate_count:
            raise ValueError("item_count cannot exceed selected_candidate_count")
        if self.date != self.digest.date:
            raise ValueError("date must match digest date")
        if self.digest_id != self.digest.digest_id:
            raise ValueError("digest_id must match digest digest_id")
        return self


@dataclass(frozen=True)
class NormalizedDocument:
    """파이프라인 내부 단계가 공유하는 정규화 문서 계약."""

    doc_id: str
    source: Source
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
class ChunkingInput:
    """pipeline 경계에서 Chunker로 넘기는 입력 계약.

    RelevanceDecision → ChunkingInput 어댑터는 service/pipeline 경계에서 처리한다.
    """

    document: NormalizedDocument
    relevance_score: float
    matched_keywords: list[str]


@dataclass
class Chunk:
    """Chunker가 출력하는 텍스트 단위."""

    chunk_id: str
    document_id: str
    chunk_index: int
    text: str
    metadata: dict[str, Any]
