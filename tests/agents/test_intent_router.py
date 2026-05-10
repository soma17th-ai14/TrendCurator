import json
from datetime import date

import pytest

from app.agents.intent_router import IntentRouter


class FakeLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[str] = []

    async def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


@pytest.mark.asyncio
async def test_intent_router_parses_llm_response_and_normalizes_intent():
    # LLM 응답을 파싱해 표준 intent 라벨로 정규화하는지 확인
    response_json = json.dumps(
        {
            "intent": "trend_comparison",
            "confidence": 0.86,
            "reasoning": "지난 7일과 이전 7일의 트렌드를 비교하라는 요청입니다.",
        }
    )
    router = IntentRouter(
        llm_client=FakeLLMClient(response=response_json),
        prompt_template="Q:{query}\nBASE:{base_date}",
    )

    result = await router.route(
        "지난 7일과 그 이전 7일의 LangGraph 트렌드 비교해줘",
        base_date=date(2026, 5, 10),
    )

    assert result.intent == "TREND_COMPARISON"
    assert result.confidence == 0.86
    assert "트렌드" in result.reasoning


@pytest.mark.asyncio
async def test_intent_router_renders_prompt_with_query_and_base_date():
    # 프롬프트 템플릿에 질문과 기준일이 정확히 삽입되는지 확인
    response_json = json.dumps(
        {
            "intent": "GENERAL_QA",
            "confidence": 0.72,
            "reasoning": "단일 질문 응답을 요청합니다.",
        }
    )
    fake = FakeLLMClient(response=response_json)
    router = IntentRouter(llm_client=fake, prompt_template="질문:{query}\n기준:{base_date}")

    await router.route("최근 HuggingFace AI Agent 동향 알려줘", base_date=date(2026, 5, 10))

    assert len(fake.calls) == 1
    assert "질문:최근 HuggingFace AI Agent 동향 알려줘" in fake.calls[0]
    assert "기준:2026-05-10" in fake.calls[0]


@pytest.mark.asyncio
async def test_intent_router_raises_on_invalid_json():
    # LLM 응답이 JSON이 아니면 예외가 발생하는지 확인
    router = IntentRouter(
        llm_client=FakeLLMClient(response="not-json"),
        prompt_template="{query}",
    )

    with pytest.raises(ValueError):
        await router.route("지난주 대비 이번주 비교", base_date=date(2026, 5, 10))
