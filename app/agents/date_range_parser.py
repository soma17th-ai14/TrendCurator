from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

from app.core.llm_client import LLMClient


@dataclass(frozen=True)
class DateRange:
    """날짜 범위 데이터 모델"""

    start: date
    end: date

    def __post_init__(self):
        if self.start > self.end:
            raise ValueError("시작일은 종료일보다 늦을 수 없습니다.")


@dataclass(frozen=True)
class DateRangeParserResult:
    """Date Range Parser의 결과 데이터 모델"""

    period_a: DateRange
    period_b: DateRange
    focus_keywords: list[str]


class DateRangeParser:
    """LLM을 이용해 자연어 질문에서 날짜 범위와 핵심 키워드를 추출"""

    def __init__(self, llm_client: LLMClient, prompt_template: str):
        self._llm_client = llm_client
        self._prompt_template = prompt_template

    async def parse(self, query: str, base_date: date) -> DateRangeParserResult:
        """주어진 질문과 기준 날짜를 기반으로 날짜 범위를 파싱"""
        prompt = self._prompt_template.format(query=query, base_date=base_date.isoformat())
        raw_response = await self._llm_client.complete(prompt)

        try:
            parsed = json.loads(raw_response)
            if not isinstance(parsed, dict):
                raise ValueError("LLM 응답이 JSON 객체 형식이 아닙니다.")
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM 응답을 JSON으로 파싱할 수 없습니다: {e}") from e

        period_a_data = parsed.get("period_a", {})
        period_b_data = parsed.get("period_b", {})

        # LLM이 {"start": ..., "end": ...} 대신 날짜 문자열을 직접 반환하는 경우 보정
        if isinstance(period_a_data, str):
            period_a_data = {"start": period_a_data, "end": period_a_data}
        if isinstance(period_b_data, str):
            period_b_data = {"start": period_b_data, "end": period_b_data}

        period_a = DateRange(
            start=date.fromisoformat(period_a_data.get("start")),
            end=date.fromisoformat(period_a_data.get("end")),
        )
        period_b = DateRange(
            start=date.fromisoformat(period_b_data.get("start")),
            end=date.fromisoformat(period_b_data.get("end")),
        )

        keywords = parsed.get("focus_keywords", [])
        if not isinstance(keywords, list) or not all(isinstance(k, str) for k in keywords):
            keywords = []

        return DateRangeParserResult(
            period_a=period_a,
            period_b=period_b,
            focus_keywords=keywords,
        )
