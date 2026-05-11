from datetime import date

from fastapi.testclient import TestClient

from app.api.query import get_query_runner
from app.graphs.query_graph import QueryGraphRunner
from app.main import app
from app.services.digest_retriever import DigestSearchResult


class FakeSearchClient:
    def search(self, **kwargs):
        return [
            DigestSearchResult(
                document_id="doc_001",
                source="huggingface",
                title="LangGraph workflow",
                url="https://example.com/langgraph",
                content="LangGraph orchestrates multi-agent workflow with graph state.",
                summary_preview="LangGraph orchestrates multi-agent workflow.",
                similarity_score=0.9,
                relevance_score=0.9,
                published_at=date(2026, 5, 10),
                matched_keywords=["langgraph", "multi-agent"],
                tags=["langgraph", "multi-agent"],
            )
        ]


class FailingSearchClient:
    def search(self, **kwargs):
        raise RuntimeError("SOLAR_API_KEY is missing")


def test_query_api_runs_graph():
    app.dependency_overrides[get_query_runner] = lambda: QueryGraphRunner(search_client=FakeSearchClient())
    try:
        client = TestClient(app)
        response = client.post(
            "/query",
            json={"question": "Summarize LangGraph workflows", "top_k": 3, "date_to": "2026-05-11"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["intent"] == "general_query"
    assert payload["data"]["sources"][0]["document_id"] == "doc_001"


def test_query_api_returns_empty_answer_when_search_fails():
    app.dependency_overrides[get_query_runner] = lambda: QueryGraphRunner(search_client=FailingSearchClient())
    try:
        client = TestClient(app)
        response = client.post(
            "/query",
            json={"question": "Summarize LangGraph workflows", "top_k": 3, "date_to": "2026-05-11"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["sources"] == []
    assert payload["data"]["warnings"]
