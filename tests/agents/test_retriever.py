"""Retriever 단위 테스트."""

from datetime import date
from unittest.mock import MagicMock

import pytest

from app.agents.retriever import Retriever, _build_where
from app.core.chroma_client import SearchResult


def make_search_result(
    doc_id: str = "doc_001",
    similarity: float = 0.9,
    published_at: str = "2026-05-10",
) -> SearchResult:
    return SearchResult(
        chunk_id=f"{doc_id}_chunk_0",
        document_id=doc_id,
        text="청크 텍스트",
        similarity_score=similarity,
        metadata={
            "document_id": doc_id,
            "source": "huggingface",
            "title": "테스트 논문",
            "url": "https://huggingface.co/papers/test",
            "published_at": published_at,
            "category": "agent",
            "relevance_score": 0.92,
            "matched_keywords": "langgraph,multi-agent",
        },
    )


def make_retriever(search_results: list[SearchResult] | None = None) -> tuple[Retriever, MagicMock, MagicMock]:
    embedding_client = MagicMock()
    embedding_client.embed_query.return_value = [0.1] * 4096

    chroma = MagicMock()
    chroma.search.return_value = search_results or [make_search_result()]

    retriever = Retriever(embedding_client, chroma)
    return retriever, embedding_client, chroma


def test_search_embeds_query():
    retriever, embedding_client, _ = make_retriever()

    retriever.search(query="멀티 에이전트")

    embedding_client.embed_query.assert_called_once_with("멀티 에이전트")


def test_search_returns_digest_results():
    retriever, _, _ = make_retriever()

    results = retriever.search(query="멀티 에이전트")

    assert len(results) == 1
    assert results[0].document_id == "doc_001"
    assert results[0].similarity_score == 0.9
    assert results[0].matched_keywords == ["langgraph", "multi-agent"]
    assert results[0].published_at == date(2026, 5, 10)


def test_search_deduplicates_by_document():
    raw = [
        make_search_result("doc_001", similarity=0.9),
        make_search_result("doc_001", similarity=0.7),  # 같은 문서, 낮은 점수
        make_search_result("doc_002", similarity=0.8),
    ]
    retriever, _, _ = make_retriever(raw)

    results = retriever.search(query="테스트", top_k=10)

    assert len(results) == 2
    doc_ids = [r.document_id for r in results]
    assert "doc_001" in doc_ids
    assert "doc_002" in doc_ids
    # doc_001은 가장 높은 점수(0.9)로 남아야 함
    doc_001_result = next(r for r in results if r.document_id == "doc_001")
    assert doc_001_result.similarity_score == 0.9


def test_search_respects_top_k():
    raw = [make_search_result(f"doc_{i:03d}", similarity=1.0 - i * 0.05) for i in range(10)]
    retriever, _, _ = make_retriever(raw)

    results = retriever.search(query="테스트", top_k=3)

    assert len(results) == 3


def test_build_where_none_when_no_filters():
    result = _build_where(None, None, None)
    assert result is None


def test_build_where_date_from_only():
    # 날짜는 Python 후처리 — ChromaDB where에는 포함되지 않음
    result = _build_where(date(2026, 5, 1), None, None)
    assert result is None


def test_build_where_multiple_conditions():
    result = _build_where(date(2026, 5, 1), date(2026, 5, 10), ["huggingface"])
    assert result == {"source": {"$in": ["huggingface"]}}


def test_build_where_categories_filter():
    result = _build_where(None, None, None, ["agent", "rag"])
    assert result == {"category": {"$in": ["agent", "rag"]}}


def test_build_where_all_filters():
    result = _build_where(date(2026, 5, 1), date(2026, 5, 10), ["huggingface"], ["agent"])
    assert result is not None
    assert "$and" in result
    assert len(result["$and"]) == 2  # source + category만 포함


def test_search_passes_where_filter_to_chroma():
    retriever, _, chroma = make_retriever()

    retriever.search(query="테스트", sources=["huggingface"])

    call_kwargs = chroma.search.call_args[1]
    assert call_kwargs["where"] == {"source": {"$in": ["huggingface"]}}


def test_search_passes_categories_filter_to_chroma():
    retriever, _, chroma = make_retriever()

    retriever.search(query="테스트", categories=["agent"])

    call_kwargs = chroma.search.call_args[1]
    assert call_kwargs["where"] == {"category": {"$in": ["agent"]}}
