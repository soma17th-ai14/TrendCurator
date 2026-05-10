from __future__ import annotations

import json
from dataclasses import dataclass, field

from app.core.llm_client import LLMClient


@dataclass(frozen=True)
class QueryRewriterResult:
    """Query Rewriter의 결과 데이터 모델"""

    optimized_queries: list[str]
    search_filter: dict[str, list[str]] = field(
        default_factory=lambda: {"sources": ["huggingface", "hackernews"]}
    )


class QueryRewriter:
    """LLM을 이용해 사용자 질문을 검색에 최적화된 쿼리로 재작성"""

    def __init__(self, llm_client: LLMClient, prompt_template: str):
        self._llm_client = llm_client
        self._prompt_template = prompt_template

    async def rewrite(self, query: str) -> QueryRewriterResult:
        """주어진 질문을 재작성"""
        prompt = self._prompt_template.format(query=query)
        raw_response = await self._llm_client.complete(prompt)

        try:
            parsed = json.loads(raw_response)
            if not isinstance(parsed, dict):
                raise ValueError("LLM 응답이 JSON 객체 형식이 아닙니다.")
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM 응답을 JSON으로 파싱할 수 없습니다: {e}") from e

        queries = parsed.get("optimized_queries", [])
        if not isinstance(queries, list) or not all(isinstance(q, str) for q in queries):
            queries = []

        search_filter = parsed.get("search_filter", {})
        if not isinstance(search_filter, dict) or "sources" not in search_filter:
            search_filter = {"sources": ["huggingface", "hackernews"]}

        return QueryRewriterResult(
            optimized_queries=queries,
            search_filter=search_filter,
        )
