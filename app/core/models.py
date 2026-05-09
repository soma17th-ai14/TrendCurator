"""공통 데이터 모델.

api-spec.md 11장 Document 모델을 Pydantic v2로 구현한다.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

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
