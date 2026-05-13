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
from app.api.responses import ErrorResponse, error_response
from app.prompts.query_agents import (
    load_query_date_range_parser_prompt,
    load_query_intent_router_prompt,
    load_query_rewriter_prompt,
)

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
    error: ErrorResponse | None = None


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
        return QueryResponse(
            success=False,
            error=error_response("QUERY_EXECUTION_FAILED", str(exc)),
        )

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
            prompt_template=load_query_intent_router_prompt(),
        ),
        "query_rewriter": QueryRewriter(
            llm_client=llm_client,
            prompt_template=load_query_rewriter_prompt(),
        ),
        "date_range_parser": DateRangeParser(
            llm_client=llm_client,
            prompt_template=load_query_date_range_parser_prompt(),
        ),
    }
