"""LangGraph orchestration for on-demand TrendCurator queries."""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from typing import Any, Literal, TypedDict

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover - keeps imports usable before deps install
    END = "__end__"
    StateGraph = None  # type: ignore

from app.services.digest_retriever import DigestSearchResult
from app.services.groundedness import GroundednessChecker, GroundednessCheckRequest


Intent = Literal["general_query", "trend_comparison"]


class QueryGraphState(TypedDict, total=False):
    question: str
    base_date: date
    top_k: int
    intent: Intent
    retrieved_docs: list[dict[str, Any]]
    answer: str
    groundedness_score: float
    groundedness_passed: bool
    sources: list[dict[str, Any]]
    comparison_metadata: dict[str, Any]


class SearchClient:
    def search(
        self,
        *,
        query: str,
        top_k: int,
        date_from: date | None = None,
        date_to: date | None = None,
        sources: list[str] | None = None,
        categories: list[str] | None = None,
    ) -> list[DigestSearchResult]:
        ...


class QueryGraphRunner:
    """Run the query workflow through LangGraph when available."""

    def __init__(
        self,
        *,
        search_client: SearchClient,
        groundedness_checker: GroundednessChecker | None = None,
    ) -> None:
        self._search_client = search_client
        self._groundedness = groundedness_checker or GroundednessChecker()
        self._graph = self._build_graph()

    def run(self, *, question: str, top_k: int = 10, base_date: date | None = None) -> QueryGraphState:
        state: QueryGraphState = {
            "question": question,
            "top_k": top_k,
            "base_date": base_date or date.today(),
        }
        if self._graph is None:
            return self._run_sequential(state)
        return self._graph.invoke(state)

    def _build_graph(self):
        if StateGraph is None:
            return None

        graph = StateGraph(QueryGraphState)
        graph.add_node("route_intent", self._route_intent)
        graph.add_node("retrieve_general", self._retrieve_general)
        graph.add_node("retrieve_trends", self._retrieve_trends)
        graph.add_node("generate_answer", self._generate_answer)
        graph.add_node("check_groundedness", self._check_groundedness)

        graph.set_entry_point("route_intent")
        graph.add_conditional_edges(
            "route_intent",
            lambda state: state["intent"],
            {
                "general_query": "retrieve_general",
                "trend_comparison": "retrieve_trends",
            },
        )
        graph.add_edge("retrieve_general", "generate_answer")
        graph.add_edge("retrieve_trends", "generate_answer")
        graph.add_edge("generate_answer", "check_groundedness")
        graph.add_edge("check_groundedness", END)
        return graph.compile()

    def _run_sequential(self, state: QueryGraphState) -> QueryGraphState:
        state = self._route_intent(state)
        state = self._retrieve_trends(state) if state["intent"] == "trend_comparison" else self._retrieve_general(state)
        state = self._generate_answer(state)
        return self._check_groundedness(state)

    def _route_intent(self, state: QueryGraphState) -> QueryGraphState:
        question = state["question"].lower()
        trend_markers = ["비교", "지난주", "이번 주", "변화", "트렌드", "대비", "compare", "trend"]
        state["intent"] = "trend_comparison" if any(marker in question for marker in trend_markers) else "general_query"
        return state

    def _retrieve_general(self, state: QueryGraphState) -> QueryGraphState:
        results = self._search_client.search(
            query=state["question"],
            top_k=state.get("top_k", 10),
            date_to=state.get("base_date"),
        )
        state["retrieved_docs"] = [_doc_to_dict(result) for result in results]
        state["sources"] = [_source_from_doc(doc) for doc in state["retrieved_docs"]]
        return state

    def _retrieve_trends(self, state: QueryGraphState) -> QueryGraphState:
        base_date = state.get("base_date") or date.today()
        period_b_start = base_date - timedelta(days=6)
        period_a_end = period_b_start - timedelta(days=1)
        period_a_start = period_a_end - timedelta(days=6)
        top_k = state.get("top_k", 10)

        docs_a = self._search_client.search(
            query=state["question"],
            top_k=top_k,
            date_from=period_a_start,
            date_to=period_a_end,
        )
        docs_b = self._search_client.search(
            query=state["question"],
            top_k=top_k,
            date_from=period_b_start,
            date_to=base_date,
        )

        state["retrieved_docs"] = [
            {**_doc_to_dict(result), "period": "period_a"} for result in docs_a
        ] + [
            {**_doc_to_dict(result), "period": "period_b"} for result in docs_b
        ]
        state["comparison_metadata"] = _comparison_metadata(
            state["retrieved_docs"],
            period_a_start,
            period_a_end,
            period_b_start,
            base_date,
        )
        state["sources"] = [_source_from_doc(doc) for doc in state["retrieved_docs"]]
        return state

    def _generate_answer(self, state: QueryGraphState) -> QueryGraphState:
        docs = state.get("retrieved_docs", [])
        if not docs:
            state["answer"] = "No source documents were retrieved, so an answer could not be generated."
            return state

        if state["intent"] == "trend_comparison":
            metadata = state.get("comparison_metadata", {})
            new_trends = ", ".join(metadata.get("new_trends", [])) or "no explicit new trend"
            declining = ", ".join(metadata.get("declining_trends", [])) or "no explicit declining trend"
            state["answer"] = (
                "This is a comparison of retrieved documents across two periods. "
                f"Prominent recent signals: {new_trends}. "
                f"Weaker signals compared with the previous period: {declining}. "
                "Interpret this answer against the listed source documents."
            )
            return state

        top_docs = docs[: min(3, len(docs))]
        bullets = " ".join(
            f"{doc['title']}: {doc['summary_preview']}" for doc in top_docs
        )
        state["answer"] = f"Summary based on retrieved evidence: {bullets}"
        return state

    def _check_groundedness(self, state: QueryGraphState) -> QueryGraphState:
        docs = state.get("retrieved_docs", [])
        result = self._groundedness.check(GroundednessCheckRequest(
            answer=state.get("answer", ""),
            question=state.get("question"),
            contexts=[doc.get("content", "") for doc in docs],
        ))
        state["groundedness_score"] = result.score
        state["groundedness_passed"] = result.passed
        return state


def _doc_to_dict(result: DigestSearchResult) -> dict[str, Any]:
    return {
        "document_id": result.document_id,
        "title": result.title,
        "source": result.source,
        "url": result.url,
        "published_at": result.published_at.isoformat() if result.published_at else None,
        "content": result.content,
        "summary_preview": result.summary_preview,
        "similarity_score": result.similarity_score,
        "tags": result.tags or result.matched_keywords,
    }


def _source_from_doc(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "document_id": doc["document_id"],
        "title": doc["title"],
        "source": doc["source"],
        "url": doc["url"],
        "period": doc.get("period"),
    }


def _comparison_metadata(
    docs: list[dict[str, Any]],
    period_a_start: date,
    period_a_end: date,
    period_b_start: date,
    period_b_end: date,
) -> dict[str, Any]:
    tags_a = Counter(tag for doc in docs if doc.get("period") == "period_a" for tag in doc.get("tags", []))
    tags_b = Counter(tag for doc in docs if doc.get("period") == "period_b" for tag in doc.get("tags", []))
    new_trends = [tag for tag, _ in tags_b.most_common(5) if tags_b[tag] > tags_a.get(tag, 0)]
    declining = [tag for tag, _ in tags_a.most_common(5) if tags_a[tag] > tags_b.get(tag, 0)]
    return {
        "period_a": {
            "start": period_a_start.isoformat(),
            "end": period_a_end.isoformat(),
            "summary": f"{sum(tags_a.values())} tag signals from previous period",
        },
        "period_b": {
            "start": period_b_start.isoformat(),
            "end": period_b_end.isoformat(),
            "summary": f"{sum(tags_b.values())} tag signals from recent period",
        },
        "new_trends": new_trends,
        "declining_trends": declining,
    }
