from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any, Protocol

from app.agents.date_range_parser import DateRange


@dataclass(frozen=True)
class PeriodRetrievalRequest:
    """Period Retriever 요청 데이터 모델"""

    period_a: DateRange
    period_b: DateRange
    focus_keywords: list[str]
    top_k: int = 5
    sources: list[str] = field(default_factory=lambda: ["huggingface", "hackernews"])


@dataclass(frozen=True)
class PeriodSearchResult:
    """검색 클라이언트가 반환하는 최소 문서 단위"""

    doc_id: str
    content: str


@dataclass(frozen=True)
class PeriodContext:
    """기간별 검색 결과 컨텍스트"""

    period: dict[str, str]
    documents: list[dict[str, str]]
    total_count: int


@dataclass(frozen=True)
class PeriodRetrievalResult:
    """Period Retriever 결과 데이터 모델"""

    context_a: PeriodContext
    context_b: PeriodContext


class PeriodSearchClient(Protocol):
    """VectorDB 검색 클라이언트가 맞춰야 하는 최소 계약"""

    def search(
        self,
        *,
        query: str,
        top_k: int,
        date_from: date,
        date_to: date,
        sources: list[str],
    ) -> list[PeriodSearchResult]:
        ...


class PeriodRetriever:
    """두 기간에 대한 컨텍스트를 각각 검색"""

    def __init__(self, search_client: PeriodSearchClient):
        self._search_client = search_client

    def retrieve(self, request: PeriodRetrievalRequest) -> PeriodRetrievalResult:
        """두 기간에 대해 각각 문서를 검색하고 결과를 조합"""
        query = "AI Agent Trend Comparison " + " ".join(request.focus_keywords)

        context_a = self._search_one_period(query, request.period_a, request.top_k, request.sources)
        context_b = self._search_one_period(query, request.period_b, request.top_k, request.sources)

        return PeriodRetrievalResult(context_a=context_a, context_b=context_b)

    def _search_one_period(
        self, query: str, period: DateRange, top_k: int, sources: list[str]
    ) -> PeriodContext:
        """단일 기간에 대한 문서를 검색"""
        results = self._search_client.search(
            query=query,
            top_k=top_k,
            date_from=period.start,
            date_to=period.end,
            sources=sources,
        )
        return PeriodContext(
            period={"start": period.start.isoformat(), "end": period.end.isoformat()},
            documents=[{"doc_id": r.doc_id, "content": r.content} for r in results],
            total_count=len(results),
        )
