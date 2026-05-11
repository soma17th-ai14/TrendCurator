"""POST /documents/search API 테스트."""

from datetime import date
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.api.documents import get_retriever, router
from app.main import app
from app.services.digest_retriever import DigestSearchResult


def make_digest_result(doc_id: str = "doc_001") -> DigestSearchResult:
    return DigestSearchResult(
        document_id=doc_id,
        source="huggingface",
        title="테스트 논문",
        url="https://huggingface.co/papers/test",
        content="청크 텍스트 내용",
        summary_preview="청크 텍스트 내용",
        similarity_score=0.87,
        relevance_score=0.92,
        published_at=date(2026, 5, 10),
        matched_keywords=["langgraph", "multi-agent"],
    )


def make_mock_retriever(results: list[DigestSearchResult] | None = None) -> MagicMock:
    mock = MagicMock()
    mock.search.return_value = results or [make_digest_result()]
    return mock


@pytest.fixture
def client():
    mock_retriever = make_mock_retriever()
    app.dependency_overrides[get_retriever] = lambda: mock_retriever
    yield TestClient(app), mock_retriever
    app.dependency_overrides.clear()


def test_search_returns_success(client):
    test_client, _ = client
    response = test_client.post(
        "/api/v1/documents/search",
        json={"query": "멀티 에이전트 프레임워크"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["error"] is None
    assert len(data["data"]["results"]) == 1


def test_search_rewritten_query_matches_input(client):
    test_client, _ = client
    response = test_client.post(
        "/api/v1/documents/search",
        json={"query": "RAG 파이프라인"},
    )
    assert response.json()["data"]["rewritten_query"] == "RAG 파이프라인"


def test_search_result_fields(client):
    test_client, _ = client
    response = test_client.post(
        "/api/v1/documents/search",
        json={"query": "테스트"},
    )
    result = response.json()["data"]["results"][0]
    assert result["document_id"] == "doc_001"
    assert result["title"] == "테스트 논문"
    assert result["similarity_score"] == 0.87
    assert result["published_at"] == "2026-05-10"


def test_search_passes_filters_to_retriever(client):
    test_client, mock_retriever = client
    test_client.post(
        "/api/v1/documents/search",
        json={
            "query": "에이전트",
            "top_k": 5,
            "date_from": "2026-05-01",
            "date_to": "2026-05-10",
            "sources": ["huggingface"],
            "categories": ["agent", "rag"],
        },
    )
    mock_retriever.search.assert_called_once()
    call_kwargs = mock_retriever.search.call_args[1]
    assert call_kwargs["top_k"] == 5
    assert call_kwargs["date_from"] == date(2026, 5, 1)
    assert call_kwargs["date_to"] == date(2026, 5, 10)
    assert call_kwargs["sources"] == ["huggingface"]
    assert call_kwargs["categories"] == ["agent", "rag"]


def test_search_empty_results(client):
    test_client, mock_retriever = client
    mock_retriever.search.return_value = []
    response = test_client.post(
        "/api/v1/documents/search",
        json={"query": "없는 주제"},
    )
    assert response.status_code == 200
    assert response.json()["data"]["results"] == []
