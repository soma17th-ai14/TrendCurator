from datetime import date

from fastapi.testclient import TestClient

from app.agents.date_range_parser import DateRange, DateRangeParserResult
from app.agents.intent_router import IntentRouterResult
from app.agents.query_rewriter import QueryRewriterResult
from app.api.query import get_query_runner
from app.graphs.query_graph import QueryGraphRunner
from app.main import app
from app.services.digest_retriever import DigestSearchResult
from app.services.period_retriever import PeriodContext, PeriodRetrievalResult


class FakeSearchClient:
    def __init__(self) -> None:
        self.calls = []

    def search(self, **kwargs):
        self.calls.append(kwargs)
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


class FakeIntentRouter:
    def __init__(self, intent="GENERAL_QA") -> None:
        self.intent = intent
        self.calls = []

    async def route(self, query, base_date):
        self.calls.append({"query": query, "base_date": base_date})
        return IntentRouterResult(intent=self.intent, confidence=0.91, reasoning="fake")


class FakeQueryRewriter:
    def __init__(self) -> None:
        self.calls = []

    async def rewrite(self, query):
        self.calls.append(query)
        return QueryRewriterResult(
            optimized_queries=["optimized LangGraph workflow query"],
            search_filter={"sources": ["huggingface", "hackernews"]},
        )


class FakeDateRangeParser:
    def __init__(self) -> None:
        self.calls = []

    async def parse(self, query, base_date):
        self.calls.append({"query": query, "base_date": base_date})
        return DateRangeParserResult(
            period_a=DateRange(start=date(2026, 4, 27), end=date(2026, 5, 3)),
            period_b=DateRange(start=date(2026, 5, 4), end=date(2026, 5, 10)),
            focus_keywords=["LangGraph"],
        )


class FakePeriodRetriever:
    def __init__(self) -> None:
        self.calls = []

    def retrieve(self, request):
        self.calls.append(request)
        return PeriodRetrievalResult(
            context_a=PeriodContext(
                period={"start": request.period_a.start.isoformat(), "end": request.period_a.end.isoformat()},
                documents=[{"doc_id": "doc_a", "content": "LangGraph planning was common."}],
                total_count=1,
            ),
            context_b=PeriodContext(
                period={"start": request.period_b.start.isoformat(), "end": request.period_b.end.isoformat()},
                documents=[{"doc_id": "doc_b", "content": "LangGraph multi-agent workflows increased."}],
                total_count=1,
            ),
        )


def test_query_api_runs_graph():
    app.dependency_overrides[get_query_runner] = lambda: QueryGraphRunner(search_client=FakeSearchClient())
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/query",
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
            "/api/v1/query",
            json={"question": "Summarize LangGraph workflows", "top_k": 3, "date_to": "2026-05-11"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["sources"] == []
    assert payload["data"]["warnings"]


def test_query_graph_uses_intent_router_and_query_rewriter():
    router = FakeIntentRouter(intent="GENERAL_QA")
    rewriter = FakeQueryRewriter()
    search_client = FakeSearchClient()
    runner = QueryGraphRunner(
        search_client=search_client,
        intent_router=router,
        query_rewriter=rewriter,
    )

    state = runner.run(
        question="Summarize LangGraph workflows",
        top_k=3,
        base_date=date(2026, 5, 11),
    )

    assert router.calls
    assert rewriter.calls == ["Summarize LangGraph workflows"]
    assert state["intent"] == "GENERAL_QA"
    assert state["rewritten_query"] == "optimized LangGraph workflow query"
    assert state["router_confidence"] == 0.91
    assert state["router_reasoning"] == "fake"
    assert state.get("warnings", []) == []
    assert search_client.calls[0]["sources"] == ["huggingface", "hackernews"]


def test_query_graph_uses_date_range_parser_and_period_retriever():
    router = FakeIntentRouter(intent="TREND_COMPARISON")
    parser = FakeDateRangeParser()
    period_retriever = FakePeriodRetriever()
    runner = QueryGraphRunner(
        search_client=FakeSearchClient(),
        intent_router=router,
        date_range_parser=parser,
        period_retriever=period_retriever,
    )

    state = runner.run(
        question="Compare LangGraph trends",
        top_k=3,
        base_date=date(2026, 5, 11),
    )

    assert parser.calls
    assert period_retriever.calls
    assert state["intent"] == "TREND_COMPARISON"
    assert state["comparison_metadata"]["period_a"]["start"] == "2026-04-27"
    assert state["comparison_metadata"]["period_b"]["end"] == "2026-05-10"
