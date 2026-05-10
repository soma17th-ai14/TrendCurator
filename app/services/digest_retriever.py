"""Daily Digest 후보 문서 검색 정책."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any, Protocol

from app.core.models import DailyDigestRetrievalRequest, DailyDigestRetrievalResult, DigestCandidate, Source


@dataclass(frozen=True)
class DigestSearchResult:
    """검색 계층이 Daily Digest Retriever에 넘기는 문서 결과."""

    document_id: str
    source: Source
    title: str
    url: str
    content: str
    summary_preview: str
    similarity_score: float
    relevance_score: float
    published_at: date | None = None
    matched_keywords: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentSearchClient(Protocol):
    """VectorDB 검색 구현이 맞춰야 하는 최소 계약."""

    def search(
        self,
        *,
        query: str,
        top_k: int,
        date_from: date,
        date_to: date,
        sources: list[Source],
    ) -> list[DigestSearchResult]:
        ...


@dataclass(frozen=True)
class DailyDigestRetriever:
    """Digest 생성에 사용할 후보 문서를 검색하고 랭킹합니다."""

    search_client: DocumentSearchClient

    def retrieve(self, request: DailyDigestRetrievalRequest) -> DailyDigestRetrievalResult:
        date_from = self._date_from(request)
        search_results = self.search_client.search(
            query=self._query(request),
            top_k=request.top_k * 3,
            date_from=date_from,
            date_to=request.digest_date,
            sources=request.sources,
        )
        candidates = self._rank_candidates(
            search_results=search_results,
            min_relevance_score=request.min_relevance_score,
        )
        selected_candidates = candidates[: request.top_k]

        return DailyDigestRetrievalResult(
            digest_date=request.digest_date,
            candidates=selected_candidates,
            total_count=len(candidates),
            selected_count=len(selected_candidates),
        )

    def _date_from(self, request: DailyDigestRetrievalRequest) -> date:
        return request.digest_date - timedelta(days=request.lookback_days)

    def _query(self, request: DailyDigestRetrievalRequest) -> str:
        if request.profile_based and request.keywords:
            return "AI Agent Daily Digest " + " ".join(request.keywords)
        return "AI Agent Daily Digest"

    def _rank_candidates(
        self,
        *,
        search_results: list[DigestSearchResult],
        min_relevance_score: float,
    ) -> list[DigestCandidate]:
        unique_results: dict[str, DigestSearchResult] = {}
        for result in search_results:
            if result.relevance_score < min_relevance_score:
                continue

            previous = unique_results.get(result.document_id)
            if previous is None or self._sort_key(result) > self._sort_key(previous):
                unique_results[result.document_id] = result

        ranked_results = sorted(unique_results.values(), key=self._sort_key, reverse=True)
        return [self._to_candidate(result) for result in ranked_results]

    def _sort_key(self, result: DigestSearchResult) -> tuple[float, float, date, str]:
        published_at = result.published_at or date.min
        return (result.relevance_score, result.similarity_score, published_at, result.title)

    def _to_candidate(self, result: DigestSearchResult) -> DigestCandidate:
        return DigestCandidate(
            document_id=result.document_id,
            source=result.source,
            title=result.title,
            url=result.url,
            published_at=result.published_at,
            content=result.content,
            summary_preview=result.summary_preview or self._summary_preview(result.content),
            similarity_score=result.similarity_score,
            relevance_score=result.relevance_score,
            matched_keywords=result.matched_keywords,
            tags=result.tags,
            metadata=result.metadata,
        )

    def _summary_preview(self, content: str) -> str:
        return content.strip()[:240]
