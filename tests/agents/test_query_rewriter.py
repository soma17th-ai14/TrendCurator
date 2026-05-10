import json

import pytest

from app.agents.query_rewriter import QueryRewriter


class FakeLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[str] = []

    async def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


@pytest.mark.asyncio
async def test_query_rewriter_parses_optimized_queries_and_filter():
    # LLM 응답에서 최적화 쿼리와 검색 필터를 올바르게 파싱하는지 확인
    response_json = json.dumps(
        {
            "optimized_queries": [
                "recent HuggingFace AI agent framework trends",
                "AI agent orchestration latest research",
            ],
            "search_filter": {"sources": ["huggingface", "hackernews"]},
        }
    )
    rewriter = QueryRewriter(
        llm_client=FakeLLMClient(response=response_json),
        prompt_template="Q:{query}",
    )

    result = await rewriter.rewrite("최근 HuggingFace에서 주목받는 AI Agent 기술은?")

    assert result.optimized_queries == [
        "recent HuggingFace AI agent framework trends",
        "AI agent orchestration latest research",
    ]
    assert result.search_filter == {"sources": ["huggingface", "hackernews"]}


@pytest.mark.asyncio
async def test_query_rewriter_defaults_sources_when_missing():
    # sources 필드가 없을 때 기본 소스를 채우는지 확인
    response_json = json.dumps({"optimized_queries": ["AI agent trends"]})
    rewriter = QueryRewriter(
        llm_client=FakeLLMClient(response=response_json),
        prompt_template="{query}",
    )

    result = await rewriter.rewrite("AI agent 최신 동향")

    assert result.search_filter == {"sources": ["huggingface", "hackernews"]}


@pytest.mark.asyncio
async def test_query_rewriter_renders_prompt():
    # 프롬프트 템플릿에 질문이 정확히 삽입되는지 확인
    response_json = json.dumps({"optimized_queries": ["query"], "search_filter": {}})
    fake = FakeLLMClient(response=response_json)
    rewriter = QueryRewriter(llm_client=fake, prompt_template="질문:{query}")

    await rewriter.rewrite("RAG와 에이전트 차이")

    assert len(fake.calls) == 1
    assert "질문:RAG와 에이전트 차이" in fake.calls[0]


@pytest.mark.asyncio
async def test_query_rewriter_raises_on_invalid_json():
    # LLM 응답이 JSON이 아니면 예외가 발생하는지 확인
    rewriter = QueryRewriter(
        llm_client=FakeLLMClient(response="not-json"),
        prompt_template="{query}",
    )

    with pytest.raises(ValueError):
        await rewriter.rewrite("멀티 에이전트 트렌드")
