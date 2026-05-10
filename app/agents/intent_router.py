from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from typing import Literal

from app.core.llm_client import LLMClient

Intent = Literal["TREND_COMPARISON", "GENERAL_QA"]


@dataclass(frozen=True)
class IntentRouterResult:
    """Intent Router의 결과 데이터 모델"""

    intent: Intent
    confidence: float
    reasoning: str


class IntentRouter:
    """LLM을 이용해 사용자 질문의 의도를 분류"""

    def __init__(self, llm_client: LLMClient, prompt_template: str):
        self._llm_client = llm_client
        self._prompt_template = prompt_template

    async def route(self, query: str, base_date: date) -> IntentRouterResult:
        """주어진 질문과 기준 날짜를 기반으로 의도를 분류"""
        prompt = self._prompt_template.format(query=query, base_date=base_date.isoformat())
        raw_response = await self._llm_client.complete(prompt)

        try:
            parsed = json.loads(raw_response)
            if not isinstance(parsed, dict):
                raise ValueError("LLM 응답이 JSON 객체 형식이 아닙니다.")
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM 응답을 JSON으로 파싱할 수 없습니다: {e}") from e

        intent_str = str(parsed.get("intent", "GENERAL_QA")).upper()
        if intent_str not in ("TREND_COMPARISON", "GENERAL_QA"):
            intent_str = "GENERAL_QA"

        return IntentRouterResult(
            intent=intent_str,  # type: ignore
            confidence=float(parsed.get("confidence", 0.0)),
            reasoning=str(parsed.get("reasoning", "")),
        )
