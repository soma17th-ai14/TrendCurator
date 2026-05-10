import json
from datetime import date

import pytest

from app.agents.date_range_parser import DateRangeParser


class FakeLLMClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls: list[str] = []

    async def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


@pytest.mark.asyncio
async def test_date_range_parser_parses_periods_and_keywords():
    # LLM 응답에서 기간과 키워드를 올바르게 파싱하는지 확인
    response_json = json.dumps(
        {
            "period_a": {"start": "2026-04-27", "end": "2026-05-03"},
            "period_b": {"start": "2026-05-04", "end": "2026-05-10"},
            "focus_keywords": ["LangGraph", "multi-agent"],
        }
    )
    parser = DateRangeParser(
        llm_client=FakeLLMClient(response=response_json),
        prompt_template="Q:{query}\nBASE:{base_date}",
    )

    result = await parser.parse(
        "지난 7일과 그 이전 7일의 LangGraph 트렌드 비교해줘",
        base_date=date(2026, 5, 10),
    )

    assert result.period_a.start == date(2026, 4, 27)
    assert result.period_a.end == date(2026, 5, 3)
    assert result.period_b.start == date(2026, 5, 4)
    assert result.period_b.end == date(2026, 5, 10)
    assert result.focus_keywords == ["LangGraph", "multi-agent"]


@pytest.mark.asyncio
async def test_date_range_parser_renders_prompt():
    # 프롬프트 템플릿에 질문과 기준일이 정확히 삽입되는지 확인
    response_json = json.dumps(
        {
            "period_a": {"start": "2026-04-27", "end": "2026-05-03"},
            "period_b": {"start": "2026-05-04", "end": "2026-05-10"},
            "focus_keywords": ["LangGraph"],
        }
    )
    fake = FakeLLMClient(response=response_json)
    parser = DateRangeParser(llm_client=fake, prompt_template="질문:{query}\n기준:{base_date}")

    await parser.parse("지난 7일 트렌드", base_date=date(2026, 5, 10))

    assert len(fake.calls) == 1
    assert "질문:지난 7일 트렌드" in fake.calls[0]
    assert "기준:2026-05-10" in fake.calls[0]


@pytest.mark.asyncio
async def test_date_range_parser_rejects_invalid_date_order():
    # 기간 시작일이 종료일보다 늦으면 예외가 발생하는지 확인
    response_json = json.dumps(
        {
            "period_a": {"start": "2026-05-10", "end": "2026-05-03"},
            "period_b": {"start": "2026-05-04", "end": "2026-05-10"},
            "focus_keywords": ["LangGraph"],
        }
    )
    parser = DateRangeParser(
        llm_client=FakeLLMClient(response=response_json),
        prompt_template="{query}",
    )

    with pytest.raises(ValueError):
        await parser.parse("지난 7일 트렌드", base_date=date(2026, 5, 10))


@pytest.mark.asyncio
async def test_date_range_parser_raises_on_invalid_json():
    # LLM 응답이 JSON이 아니면 예외가 발생하는지 확인
    parser = DateRangeParser(
        llm_client=FakeLLMClient(response="not-json"),
        prompt_template="{query}",
    )

    with pytest.raises(ValueError):
        await parser.parse("지난주 대비 이번주", base_date=date(2026, 5, 10))
