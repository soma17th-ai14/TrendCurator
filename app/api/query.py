"""On-demand query and trend comparison API."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.retriever import Retriever
from app.api.documents import get_retriever
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


class QueryResponse(BaseModel):
    success: bool
    data: QueryData | None = None
    error: str | None = None


def get_query_runner(retriever: Retriever = Depends(get_retriever)) -> QueryGraphRunner:
    return QueryGraphRunner(search_client=retriever)


@router.post("/query", response_model=QueryResponse)
def run_query(
    request: QueryRequest,
    runner: QueryGraphRunner = Depends(get_query_runner),
) -> QueryResponse:
    state = runner.run(
        question=request.question,
        top_k=request.top_k,
        base_date=request.date_to,
    )
    return QueryResponse(
        success=True,
        data=QueryData(
            intent=state["intent"],
            answer=state.get("answer", ""),
            groundedness_score=state.get("groundedness_score", 0.0),
            groundedness_passed=state.get("groundedness_passed", False),
            sources=state.get("sources", []),
            comparison_metadata=state.get("comparison_metadata"),
        ),
    )
