"""LangGraph orchestration for on-demand TrendCurator queries."""

from __future__ import annotations

import asyncio
import logging
from collections import Counter
from datetime import date, timedelta
from typing import Any, Literal, Protocol, TypedDict

try:
    from langgraph.graph import END, StateGraph
except Exception:  # pragma: no cover - keeps imports usable before deps install
    END = "__end__"
    StateGraph = None  # type: ignore

from app.agents.date_range_parser import DateRange, DateRangeParser
from app.agents.intent_router import IntentRouter
from app.agents.query_rewriter import QueryRewriter
from app.core.llm_client import LLMClient
from app.services.digest_retriever import DigestSearchResult
from app.services.groundedness import GroundednessChecker, GroundednessCheckRequest
from app.services.period_retriever import (
    PeriodContext,
    PeriodRetrievalRequest,
    PeriodRetrievalResult,
    PeriodRetriever,
    PeriodSearchResult,
)


Intent = Literal["GENERAL_QA", "TREND_COMPARISON"]
logger = logging.getLogger(__name__)
VALID_SEARCH_SOURCES = {"huggingface", "hackernews"}


class QueryGraphState(TypedDict, total=False):
    question: str
    base_date: date
    top_k: int
    intent: Intent
    rewritten_query: str
    search_sources: list[str]
    router_reasoning: str
    router_confidence: float
    retrieved_docs: list[dict[str, Any]]
    answer: str
    groundedness_score: float
    groundedness_passed: bool
    sources: list[dict[str, Any]]
    comparison_metadata: dict[str, Any]
    warnings: list[str]
    skip_groundedness: bool


class SearchClient(Protocol):
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
    """Run the query workflow with PR #24 agents wired into LangGraph."""

    def __init__(
        self,
        *,
        search_client: SearchClient,
        intent_router: IntentRouter | None = None,
        query_rewriter: QueryRewriter | None = None,
        date_range_parser: DateRangeParser | None = None,
        period_retriever: PeriodRetriever | None = None,
        groundedness_checker: GroundednessChecker | None = None,
        llm_client: LLMClient | None = None,
    ) -> None:
        self._search_client = search_client
        self._intent_router = intent_router
        self._query_rewriter = query_rewriter
        self._date_range_parser = date_range_parser
        self._period_retriever = period_retriever  # None이면 search_client 직접 호출 경로 사용
        self._groundedness = groundedness_checker or GroundednessChecker()
        self._llm_client = llm_client
        self._graph = self._build_graph()

    def run(self, *, question: str, top_k: int = 10, base_date: date | None = None) -> QueryGraphState:
        state: QueryGraphState = {
            "question": question,
            "top_k": top_k,
            "base_date": base_date or date.today(),
        }
        if _is_small_talk(question):
            return {
                **state,
                "intent": "GENERAL_QA",
                "answer": "안녕하세요. AI 트렌드, 수집 문서, 다이제스트에 대해 궁금한 내용을 물어보세요.",
                "retrieved_docs": [],
                "sources": [],
                "groundedness_score": 1.0,
                "groundedness_passed": True,
                "skip_groundedness": True,
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
                "GENERAL_QA": "retrieve_general",
                "TREND_COMPARISON": "retrieve_trends",
            },
        )
        graph.add_edge("retrieve_general", "generate_answer")
        graph.add_edge("retrieve_trends", "generate_answer")
        graph.add_edge("generate_answer", "check_groundedness")
        graph.add_edge("check_groundedness", END)
        return graph.compile()

    def _run_sequential(self, state: QueryGraphState) -> QueryGraphState:
        state = self._route_intent(state)
        state = self._retrieve_trends(state) if state["intent"] == "TREND_COMPARISON" else self._retrieve_general(state)
        state = self._generate_answer(state)
        return self._check_groundedness(state)

    def _route_intent(self, state: QueryGraphState) -> QueryGraphState:
        if self._intent_router is not None:
            try:
                result = _run_async(self._intent_router.route(
                    state["question"],
                    state.get("base_date") or date.today(),
                ))
                state["intent"] = result.intent
                state["router_confidence"] = result.confidence
                state["router_reasoning"] = result.reasoning
                return state
            except Exception as exc:
                _append_warning(state, f"IntentRouter fallback: {exc}")

        question = state["question"].lower()
        comparison_markers = [
            "compare",
            "comparison",
            "vs",
            "versus",
            "비교",
            "대비",
            "변화",
            "지난주",
            "이번 주",
            "이번주",
        ]
        state["intent"] = "TREND_COMPARISON" if any(marker in question for marker in comparison_markers) else "GENERAL_QA"
        return state

    def _retrieve_general(self, state: QueryGraphState) -> QueryGraphState:
        rewritten_query = self._rewrite_query(state)
        results = self._safe_search(
            state,
            query=rewritten_query,
            top_k=state.get("top_k", 10),
            date_to=state.get("base_date"),
            sources=state.get("search_sources"),
        )
        state["rewritten_query"] = rewritten_query
        state["retrieved_docs"] = [_doc_to_dict(result) for result in results]
        state["sources"] = [_source_from_doc(doc) for doc in state["retrieved_docs"]]
        return state

    def _retrieve_trends(self, state: QueryGraphState) -> QueryGraphState:
        base_date = state.get("base_date") or date.today()
        top_k = state.get("top_k", 10)
        ranges = self._parse_date_ranges(state, base_date)
        period_a = ranges["period_a"]
        period_b = ranges["period_b"]
        focus_keywords = ranges["focus_keywords"]

        if self._period_retriever is not None:
            # 명시적으로 주입된 PeriodRetriever를 사용 (주로 테스트용)
            retrieval = self._retrieve_period_contexts(
                state,
                period_a=period_a,
                period_b=period_b,
                focus_keywords=focus_keywords,
                top_k=top_k,
            )
            retrieved_docs = [
                _period_doc_to_dict(doc, "period_a")
                for doc in retrieval.context_a.documents
            ] + [
                _period_doc_to_dict(doc, "period_b")
                for doc in retrieval.context_b.documents
            ]
        else:
            # 기본 경로: Retriever(PR #22)를 직접 호출해 DigestSearchResult 전체 메타데이터 보존
            query = "AI Agent Trend Comparison " + " ".join(focus_keywords)
            results_a = self._safe_search(
                state, query=query, top_k=top_k,
                date_from=period_a.start, date_to=period_a.end,
            )
            results_b = self._safe_search(
                state, query=query, top_k=top_k,
                date_from=period_b.start, date_to=period_b.end,
            )
            retrieved_docs = (
                [{**_doc_to_dict(r), "period": "period_a"} for r in results_a]
                + [{**_doc_to_dict(r), "period": "period_b"} for r in results_b]
            )

        state["retrieved_docs"] = retrieved_docs
        state["comparison_metadata"] = _comparison_metadata(
            retrieved_docs,
            period_a.start,
            period_a.end,
            period_b.start,
            period_b.end,
        )
        state["sources"] = [_source_from_doc(doc) for doc in retrieved_docs]
        return state

    def _generate_answer(self, state: QueryGraphState) -> QueryGraphState:
        docs = state.get("retrieved_docs", [])
        if not docs:
            state["answer"] = "검색된 소스 문서가 없어 답변을 생성할 수 없습니다."
            return state

        if self._llm_client is not None:
            state["answer"] = _run_async(self._generate_answer_llm(state, docs))
            return state

        if state["intent"] == "TREND_COMPARISON":
            metadata = state.get("comparison_metadata", {})
            new_trends = ", ".join(metadata.get("new_trends", [])) or "신규 트렌드 없음"
            declining = ", ".join(metadata.get("declining_trends", [])) or "감소 트렌드 없음"
            state["answer"] = (
                "두 기간의 검색 문서를 비교한 결과입니다. "
                f"최근 기간의 주요 시그널: {new_trends}. "
                f"이전 대비 약화된 시그널: {declining}. "
                "아래 출처 문서를 참고하여 해석하세요."
            )
            return state

        top_docs = docs[: min(3, len(docs))]
        bullets = " ".join(
            f"{doc['title']}: {doc['summary_preview']}" for doc in top_docs
        )
        state["answer"] = f"검색된 문서 기반 요약: {bullets}"
        return state

    async def _generate_answer_llm(
        self, state: QueryGraphState, docs: list[dict[str, Any]]
    ) -> str:
        question = state.get("question", "")
        if state["intent"] == "TREND_COMPARISON":
            docs_a = [d for d in docs if d.get("period") == "period_a"]
            docs_b = [d for d in docs if d.get("period") == "period_b"]
            context_a = _build_context(docs_a)
            context_b = _build_context(docs_b)
            metadata = state.get("comparison_metadata") or {}
            metadata_block = _format_comparison_metadata(metadata)
            prompt = (
                "당신은 AI 트렌드 분석 전문가입니다.\n"
                "두 기간의 문서를 비교하여 트렌드 변화를 한국어로 요약하세요.\n"
                "문서에 없는 사실을 추가하지 마세요.\n"
                "[트렌드 시그널 요약]은 시스템이 두 기간 문서의 태그 빈도를 비교해 계산한 결과입니다.\n"
                "이 시그널을 답변에 반영하되, 시그널과 문서 내용이 충돌하면 문서 내용을 우선하세요.\n\n"
                f"질문: {question}\n\n"
                f"{metadata_block}\n"
                f"[이전 기간 문서]\n{context_a}\n\n"
                f"[최근 기간 문서]\n{context_b}"
            )
        else:
            top_docs = docs[: min(5, len(docs))]
            context = _build_context(top_docs)
            prompt = (
                "당신은 AI 트렌드 분석 전문가입니다.\n"
                "아래 검색된 문서를 근거로 질문에 한국어로 답변하세요.\n"
                "문서에 없는 사실을 추가하지 마세요.\n\n"
                f"질문: {question}\n\n"
                f"검색 문서:\n{context}"
            )
        return await self._llm_client.complete(prompt)

    def _check_groundedness(self, state: QueryGraphState) -> QueryGraphState:
        if state.get("skip_groundedness"):
            state.setdefault("groundedness_score", 1.0)
            state.setdefault("groundedness_passed", True)
            return state

        docs = state.get("retrieved_docs", [])
        result = self._groundedness.check(GroundednessCheckRequest(
            answer=state.get("answer", ""),
            question=state.get("question"),
            contexts=[doc.get("content", "") for doc in docs],
        ))
        state["groundedness_score"] = result.score
        state["groundedness_passed"] = result.passed
        return state

    def _safe_search(self, state: QueryGraphState, **kwargs: Any) -> list[DigestSearchResult]:
        try:
            results = self._search_client.search(**kwargs)
        except Exception as exc:
            logger.warning("query search skipped: kwargs=%s error=%s", kwargs, exc)
            _append_warning(state, f"Search skipped: {exc}")
            return []
        if not results:
            message = _empty_search_warning(kwargs)
            logger.warning("query search returned no documents: %s", message)
            _append_warning(state, message)
        return results

    def _rewrite_query(self, state: QueryGraphState) -> str:
        if self._query_rewriter is None:
            return state["question"]

        try:
            result = _run_async(self._query_rewriter.rewrite(state["question"]))
        except Exception as exc:
            _append_warning(state, f"QueryRewriter fallback: {exc}")
            return state["question"]

        if result.optimized_queries:
            sources = result.search_filter.get("sources")
            if isinstance(sources, list) and all(isinstance(source, str) for source in sources):
                valid_sources = [source for source in sources if source in VALID_SEARCH_SOURCES]
                if valid_sources:
                    state["search_sources"] = valid_sources
                elif sources:
                    _append_warning(state, f"QueryRewriter ignored invalid source filters: {sources}")
            return result.optimized_queries[0]
        return state["question"]

    def _parse_date_ranges(self, state: QueryGraphState, base_date: date) -> dict[str, Any]:
        if self._date_range_parser is not None:
            try:
                result = _run_async(self._date_range_parser.parse(state["question"], base_date))
                return {
                    "period_a": result.period_a,
                    "period_b": result.period_b,
                    "focus_keywords": result.focus_keywords,
                }
            except Exception as exc:
                _append_warning(state, f"DateRangeParser fallback: {exc}")

        period_b_start = base_date - timedelta(days=6)
        period_a_end = period_b_start - timedelta(days=1)
        period_a_start = period_a_end - timedelta(days=6)
        return {
            "period_a": DateRange(start=period_a_start, end=period_a_end),
            "period_b": DateRange(start=period_b_start, end=base_date),
            "focus_keywords": _fallback_keywords(state["question"]),
        }

    def _retrieve_period_contexts(
        self,
        state: QueryGraphState,
        *,
        period_a: DateRange,
        period_b: DateRange,
        focus_keywords: list[str],
        top_k: int,
    ) -> PeriodRetrievalResult:
        try:
            return self._period_retriever.retrieve(PeriodRetrievalRequest(
                period_a=period_a,
                period_b=period_b,
                focus_keywords=focus_keywords,
                top_k=top_k,
            ))
        except Exception as exc:
            _append_warning(state, f"PeriodRetriever skipped: {exc}")
            return PeriodRetrievalResult(
                context_a=_empty_period_context(period_a),
                context_b=_empty_period_context(period_b),
            )


class _PeriodSearchAdapter:
    def __init__(self, search_client: SearchClient) -> None:
        self._search_client = search_client

    def search(
        self,
        *,
        query: str,
        top_k: int,
        date_from: date,
        date_to: date,
        sources: list[str],
    ) -> list[PeriodSearchResult]:
        results = self._search_client.search(
            query=query,
            top_k=top_k,
            date_from=date_from,
            date_to=date_to,
            sources=sources,
        )
        return [
            PeriodSearchResult(
                doc_id=result.document_id,
                content=result.content or result.summary_preview,
            )
            for result in results
        ]


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


def _period_doc_to_dict(doc: dict[str, str], period: str) -> dict[str, Any]:
    doc_id = doc.get("doc_id", "")
    content = doc.get("content", "")
    return {
        "document_id": doc_id,
        "title": doc_id or "period document",
        "source": "",
        "url": "",
        "published_at": None,
        "content": content,
        "summary_preview": content[:200],
        "similarity_score": 0.0,
        "tags": _fallback_keywords(content),
        "period": period,
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
            "summary": f"이전 기간 태그 시그널 {sum(tags_a.values())}개",
        },
        "period_b": {
            "start": period_b_start.isoformat(),
            "end": period_b_end.isoformat(),
            "summary": f"최근 기간 태그 시그널 {sum(tags_b.values())}개",
        },
        "new_trends": new_trends,
        "declining_trends": declining,
    }


def _empty_period_context(period: DateRange) -> PeriodContext:
    return PeriodContext(
        period={"start": period.start.isoformat(), "end": period.end.isoformat()},
        documents=[],
        total_count=0,
    )


def _fallback_keywords(text: str) -> list[str]:
    terms = []
    for token in text.replace(",", " ").split():
        cleaned = token.strip(" .!?()[]{}'\"").lower()
        if len(cleaned) >= 3 and cleaned not in terms:
            terms.append(cleaned)
    return terms[:5]


def _append_warning(state: QueryGraphState, message: str) -> None:
    state.setdefault("warnings", []).append(message)


def _empty_search_warning(kwargs: dict[str, Any]) -> str:
    query = kwargs.get("query", "")
    date_from = kwargs.get("date_from")
    date_to = kwargs.get("date_to")
    sources = kwargs.get("sources")
    categories = kwargs.get("categories")
    parts = [f"Search returned no documents for query={query!r}"]
    if date_from is not None:
        parts.append(f"date_from={date_from}")
    if date_to is not None:
        parts.append(f"date_to={date_to}")
    if sources:
        parts.append(f"sources={sources}")
    if categories:
        parts.append(f"categories={categories}")
    return " ".join(parts)


def _is_small_talk(question: str) -> bool:
    normalized = question.strip().lower()
    normalized = normalized.rstrip("!.?。！？~ ")
    return normalized in {
        "안녕",
        "안녕하세요",
        "하이",
        "ㅎㅇ",
        "hello",
        "hi",
        "hey",
    }


def _format_comparison_metadata(metadata: dict[str, Any]) -> str:
    """LLM 프롬프트에 주입할 트렌드 시그널 요약 블록을 만듭니다.

    시스템이 태그 빈도로 계산한 new_trends/declining_trends 를 LLM 답변 근거로 노출합니다.
    메타데이터가 비어 있으면 빈 문자열을 반환하여 프롬프트 길이를 늘리지 않습니다.
    """
    new_trends = metadata.get("new_trends") or []
    declining = metadata.get("declining_trends") or []
    period_a = metadata.get("period_a") or {}
    period_b = metadata.get("period_b") or {}
    if not (new_trends or declining or period_a or period_b):
        return ""

    parts = ["[트렌드 시그널 요약]"]
    if period_a.get("start") and period_a.get("end"):
        parts.append(f"- 이전 기간: {period_a['start']} ~ {period_a['end']}")
    if period_b.get("start") and period_b.get("end"):
        parts.append(f"- 최근 기간: {period_b['start']} ~ {period_b['end']}")
    parts.append(
        "- 최근 기간에서 새로 부상한 태그: "
        + (", ".join(new_trends) if new_trends else "(없음)")
    )
    parts.append(
        "- 이전 대비 약화된 태그: "
        + (", ".join(declining) if declining else "(없음)")
    )
    return "\n".join(parts) + "\n"


def _build_context(docs: list[dict[str, Any]]) -> str:
    parts = []
    for doc in docs:
        title = doc.get("title") or doc.get("document_id", "")
        body = doc.get("summary_preview") or doc.get("content", "")
        if body:
            body = body[:400]
        parts.append(f"- {title}: {body}")
    return "\n".join(parts)


def _run_async(awaitable):
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(awaitable)
    raise RuntimeError("Cannot run async query agent inside an already running event loop.")
