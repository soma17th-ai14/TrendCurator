"""On-demand query and trend comparison API."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.date_range_parser import DateRangeParser
from app.agents.intent_router import IntentRouter
from app.agents.query_rewriter import QueryRewriter
from app.agents.retriever import Retriever
from app.api.documents import get_retriever
from app.core.solar_client import SolarClient
from app.core.solar_llm_client import SolarLLMClient
from app.core.settings import get_solar_settings
from app.graphs.query_graph import QueryGraphRunner

router = APIRouter()


class QueryRequest(BaseModel):
    question: str
    top_k: int = Field(default=10, ge=1, le=50)
    date_to: date | None = None


class QueryData(BaseModel):
    intent: Literal["general_query", "trend_comparison"]
    answer: str
    groundedness_score: float
    groundedness_passed: bool
    sources: list[dict[str, Any]]
    comparison_metadata: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)


class QueryResponse(BaseModel):
    success: bool
    data: QueryData | None = None
    error: str | None = None


def get_query_runner(retriever: Retriever = Depends(get_retriever)) -> QueryGraphRunner:
    agents = _build_query_agents()
    return QueryGraphRunner(
        search_client=retriever,
        intent_router=agents.get("intent_router"),
        query_rewriter=agents.get("query_rewriter"),
        date_range_parser=agents.get("date_range_parser"),
    )


@router.post("/query", response_model=QueryResponse)
def run_query(
    request: QueryRequest,
    runner: QueryGraphRunner = Depends(get_query_runner),
) -> QueryResponse:
    try:
        state = runner.run(
            question=request.question,
            top_k=request.top_k,
            base_date=request.date_to,
        )
    except Exception as exc:
        return QueryResponse(success=False, error=str(exc))

    return QueryResponse(
        success=True,
        data=QueryData(
            intent=_api_intent(state["intent"]),
            answer=state.get("answer", ""),
            groundedness_score=state.get("groundedness_score", 0.0),
            groundedness_passed=state.get("groundedness_passed", False),
            sources=state.get("sources", []),
            comparison_metadata=state.get("comparison_metadata"),
            warnings=state.get("warnings", []),
        ),
    )


def _api_intent(intent: str) -> Literal["general_query", "trend_comparison"]:
    if intent == "TREND_COMPARISON":
        return "trend_comparison"
    return "general_query"


def _build_query_agents() -> dict[str, object]:
    try:
        settings = get_solar_settings()
    except Exception:
        return {}

    solar_client = SolarClient(settings)
    llm_client = SolarLLMClient(
        solar_client=solar_client,
        model=settings.mini_model,
        temperature=0.0,
        response_format={"type": "json_object"},
    )
    return {
        "intent_router": IntentRouter(
            llm_client=llm_client,
            prompt_template=(
                "Classify the user question for TrendCurator.\n"
                "Return JSON with intent, confidence, reasoning.\n"
                "intent must be exactly TREND_COMPARISON or GENERAL_QA.\n"
                "TREND_COMPARISON: the user EXPLICITLY asks to compare two different time periods "
                "(e.g. 'compare last week vs this week', 'how did things change', '지난주 대비 이번주').\n"
                "GENERAL_QA: the user asks for a summary, explanation, or current status of a topic "
                "(e.g. 'summarize', 'what is', 'recent trends in X', 'latest papers on Y').\n"
                "When in doubt, choose GENERAL_QA.\n"
                "Question: {query}\nBase date: {base_date}"
            ),
        ),
        "query_rewriter": QueryRewriter(
            llm_client=llm_client,
            prompt_template=(
                "Rewrite the user question into 1-2 concise vector-search queries.\n"
                "Return JSON with optimized_queries and search_filter.sources.\n"
                "sources must be a list containing 'huggingface', 'hackernews', or both.\n"
                "Question: {query}"
            ),
        ),
        "date_range_parser": DateRangeParser(
            llm_client=llm_client,
            prompt_template=(
                "Extract two comparison time periods from the user question.\n"
                "Return JSON in EXACTLY this format (no other keys):\n"
                '{{"period_a": {{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}}, '
                '"period_b": {{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}}, '
                '"focus_keywords": ["keyword1", "keyword2"]}}\n'
                "period_a = the older/previous period, period_b = the more recent period.\n"
                "If no specific period is mentioned, use: "
                "period_b = 7 days ending on base_date, period_a = the 7 days before that.\n"
                "Question: {query}\nBase date: {base_date}"
            ),
        ),
    }
