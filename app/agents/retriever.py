"""VectorDB 검색 에이전트.

DocumentSearchClient 프로토콜을 구현하며
digest_retriever.DigestSearchResult 형식으로 결과를 반환한다.
"""

from __future__ import annotations

from datetime import date

from app.core.chroma_client import ChromaClient
from app.core.embedding_client import EmbeddingClient
from app.core.models import Source
from app.services.digest_retriever import DigestSearchResult


class Retriever:
    """쿼리 임베딩 → ChromaDB 검색 → 문서 단위 deduplicate."""

    def __init__(self, embedding_client: EmbeddingClient, chroma: ChromaClient) -> None:
        self._embedding = embedding_client
        self._chroma = chroma

    def search(
        self,
        *,
        query: str,
        top_k: int = 10,
        date_from: date | None = None,
        date_to: date | None = None,
        sources: list[Source] | None = None,
        categories: list[str] | None = None,
    ) -> list[DigestSearchResult]:
        query_vector = self._embedding.embed_query(query)
        where = _build_where(date_from, date_to, sources, categories)
        # 날짜 필터는 Python 후처리로 적용하므로 여분을 확보
        fetch_k = top_k * 5 if (date_from or date_to) else top_k * 3
        raw = self._chroma.search(query_vector, top_k=fetch_k, where=where)
        deduped = _deduplicate(raw, fetch_k)
        filtered = _filter_by_date(deduped, date_from, date_to)
        return filtered[:top_k]


def _build_where(
    date_from: date | None,
    date_to: date | None,
    sources: list[Source] | None,
    categories: list[str] | None = None,
) -> dict | None:
    # 날짜는 published_at(ISO 문자열)을 Python에서 필터링 — ChromaDB는 문자열 $gte/$lte 미지원
    # published_at_int 필드는 Chunker에 기록되지만, 기존 데이터 호환성을 위해 아직 WHERE에 미사용
    conditions = []
    if sources:
        conditions.append({"source": {"$in": list(sources)}})
    if categories:
        conditions.append({"category": {"$in": list(categories)}})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def _filter_by_date(
    results: list[DigestSearchResult],
    date_from: date | None,
    date_to: date | None,
) -> list[DigestSearchResult]:
    if date_from is None and date_to is None:
        return results
    filtered = []
    for r in results:
        if r.published_at is None:
            continue
        if date_from and r.published_at < date_from:
            continue
        if date_to and r.published_at > date_to:
            continue
        filtered.append(r)
    return filtered



def _deduplicate(raw_results, top_k: int) -> list[DigestSearchResult]:
    best: dict = {}
    for r in raw_results:
        doc_id = r.document_id or r.chunk_id
        if doc_id not in best or r.similarity_score > best[doc_id].similarity_score:
            best[doc_id] = r

    ranked = sorted(best.values(), key=lambda x: x.similarity_score, reverse=True)[:top_k]
    return [_to_digest_result(r) for r in ranked]


def _to_digest_result(r) -> DigestSearchResult:
    meta = r.metadata
    raw_keywords = meta.get("matched_keywords", "")
    matched_keywords = raw_keywords.split(",") if isinstance(raw_keywords, str) and raw_keywords else []

    published_at_str = meta.get("published_at")
    published_at = date.fromisoformat(published_at_str) if published_at_str else None

    return DigestSearchResult(
        document_id=r.document_id,
        source=meta.get("source", ""),
        title=meta.get("title", ""),
        url=meta.get("url", ""),
        content=r.text,
        summary_preview=r.text[:200],
        similarity_score=r.similarity_score,
        relevance_score=float(meta.get("relevance_score", 0.0)),
        published_at=published_at,
        matched_keywords=matched_keywords,
    )
