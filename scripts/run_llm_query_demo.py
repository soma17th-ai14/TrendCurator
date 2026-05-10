from __future__ import annotations

import argparse
import asyncio
import json
from datetime import date

from app.agents.date_range_parser import DateRangeParser
from app.agents.intent_router import IntentRouter
from app.agents.query_rewriter import QueryRewriter
from app.core.settings import get_solar_settings
from app.core.solar_client import SolarClient
from app.core.solar_llm_client import SolarLLMClient
from app.services.period_retriever import (
    PeriodRetrievalRequest,
    PeriodRetriever,
    PeriodSearchResult,
)

INTENT_PROMPT = """당신은 사용자 질문의 의도를 분류합니다.
다음 JSON 형식으로만 응답하세요.
{{
    "intent": "TREND_COMPARISON" 또는 "GENERAL_QA",
    "confidence": 0.0에서 1.0 사이 숫자,
    "reasoning": "한 줄 설명"
}}

질문: {query}
기준일: {base_date}
"""

REWRITE_PROMPT = """당신은 질문을 VectorDB 검색에 최적화된 쿼리로 재작성합니다.
다음 JSON 형식으로만 응답하세요.
{{
    "optimized_queries": ["query 1", "query 2"],
    "search_filter": {{"sources": ["huggingface", "hackernews"]}}
}}

질문: {query}
"""

DATE_RANGE_PROMPT = """당신은 질문에서 비교 기간과 핵심 키워드를 추출합니다.
다음 JSON 형식으로만 응답하세요.
{{
    "period_a": {{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}},
    "period_b": {{"start": "YYYY-MM-DD", "end": "YYYY-MM-DD"}},
    "focus_keywords": ["키워드1", "키워드2"]
}}

질문: {query}
기준일: {base_date}
"""


class EmptyPeriodSearchClient:
    """VectorDB 연동 전 임시 검색 클라이언트"""

    def search(self, *, query: str, top_k: int, date_from: date, date_to: date, sources: list[str]) -> list[PeriodSearchResult]:
        return []


async def run(query: str, base_date: date) -> None:
    settings = get_solar_settings()
    solar_client = SolarClient(settings)
    llm_client = SolarLLMClient(
        solar_client=solar_client,
        model=settings.mini_model,
        temperature=0.1,
        response_format={"type": "json_object"},
    )

    intent_router = IntentRouter(llm_client=llm_client, prompt_template=INTENT_PROMPT)
    query_rewriter = QueryRewriter(llm_client=llm_client, prompt_template=REWRITE_PROMPT)
    date_range_parser = DateRangeParser(llm_client=llm_client, prompt_template=DATE_RANGE_PROMPT)

    intent_result = await intent_router.route(query, base_date)
    print("intent_result=", json.dumps(intent_result.__dict__, ensure_ascii=False))

    if intent_result.intent == "GENERAL_QA":
        rewrite_result = await query_rewriter.rewrite(query)
        print("query_rewriter=", json.dumps(rewrite_result.__dict__, ensure_ascii=False))
        return

    range_result = await date_range_parser.parse(query, base_date)
    print(
        "date_range_parser=",
        json.dumps(
            {
                "period_a": {
                    "start": range_result.period_a.start.isoformat(),
                    "end": range_result.period_a.end.isoformat(),
                },
                "period_b": {
                    "start": range_result.period_b.start.isoformat(),
                    "end": range_result.period_b.end.isoformat(),
                },
                "focus_keywords": range_result.focus_keywords,
            },
            ensure_ascii=False,
        ),
    )

    retriever = PeriodRetriever(search_client=EmptyPeriodSearchClient())
    retrieval_result = retriever.retrieve(
        PeriodRetrievalRequest(
            period_a=range_result.period_a,
            period_b=range_result.period_b,
            focus_keywords=range_result.focus_keywords,
            top_k=5,
        )
    )
    print(
        "period_retriever=",
        json.dumps(
            {
                "context_a": retrieval_result.context_a.__dict__,
                "context_b": retrieval_result.context_b.__dict__,
            },
            ensure_ascii=False,
        ),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="LLM 연결 데모")
    parser.add_argument("query", help="사용자 질문")
    parser.add_argument("--date-to", dest="date_to", help="기준일(YYYY-MM-DD)")
    args = parser.parse_args()

    base_date = date.fromisoformat(args.date_to) if args.date_to else date.today()
    asyncio.run(run(args.query, base_date))


if __name__ == "__main__":
    main()
