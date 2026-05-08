"""공통 데이터 모델.

api-spec.md 11장 Document 모델을 Pydantic v2로 구현한다.
"""

from datetime import date, datetime
from typing import Literal

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
    metadata: dict = Field(default_factory=dict)
