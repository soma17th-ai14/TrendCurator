"""Solar Mini 기반 관련성 필터."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Protocol

from app.agents.relevance_filter import RelevanceDecision, SolarMiniRelevanceFilter
from app.core.models import NormalizedDocument
from app.core.settings import SolarSettings
from app.core.solar_client import SolarClient, SolarMessage


PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "solar_mini_relevance.md"


class SolarJsonClient(Protocol):
    def chat_json(
        self,
        *,
        model: str,
        messages: list[SolarMessage],
        temperature: float = 0.2,
    ) -> dict:
        ...


@dataclass(frozen=True)
class SolarMiniLLMRelevanceFilter:
    """정규화된 문서가 AI Agent 관련 정보인지 Solar Mini에 판정시킵니다."""

    client: SolarJsonClient
    settings: SolarSettings
    fallback_filter: SolarMiniRelevanceFilter = SolarMiniRelevanceFilter()

    @classmethod
    def from_settings(cls, settings: SolarSettings) -> "SolarMiniLLMRelevanceFilter":
        return cls(client=SolarClient(settings), settings=settings)

    def evaluate(self, document: NormalizedDocument) -> RelevanceDecision:
        # Solar 응답이 일부 필드를 누락하거나 타입이 흔들려도
        # 파이프라인이 깨지지 않도록 로컬 fallback 판정을 기본값으로 사용합니다.
        fallback = self.fallback_filter.evaluate(document)
        try:
            result = self.client.chat_json(
                model=self.settings.mini_model,
                messages=[
                    SolarMessage(role="system", content=self._load_system_prompt()),
                    SolarMessage(role="user", content=self._format_document(document)),
                ],
                temperature=0.0,
            )
        except Exception:
            return fallback

        if not isinstance(result, dict):
            return fallback

        score = self._parse_score(result.get("score"), fallback.score)
        matched_keywords = result.get("matched_keywords", fallback.matched_keywords)
        if not isinstance(matched_keywords, list):
            matched_keywords = fallback.matched_keywords

        parsed_is_relevant = self._parse_bool(result.get("is_relevant"), fallback.is_relevant)
        is_relevant = parsed_is_relevant and score >= self.fallback_filter.threshold

        return RelevanceDecision(
            document=document,
            is_relevant=is_relevant,
            score=round(score, 4),
            matched_keywords=[str(keyword) for keyword in matched_keywords],
            reason=str(result.get("reason", fallback.reason)),
        )

    def filter(self, documents: list[NormalizedDocument]) -> list[RelevanceDecision]:
        return [decision for decision in map(self.evaluate, documents) if decision.is_relevant]

    def _format_document(self, document: NormalizedDocument) -> str:
        return (
            f"title: {document.title}\n"
            f"source: {document.source}\n"
            f"published_date: {document.published_date}\n"
            f"category_hint: {document.category_hint}\n"
            f"external_id: {document.external_id}\n"
            f"raw_text:\n{document.raw_text}"
        )

    def _parse_bool(self, value: object, fallback: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered == "true":
                return True
            if lowered == "false":
                return False
        return fallback

    def _parse_score(self, value: object, fallback: float) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            return fallback
        if not math.isfinite(score):
            return fallback
        return min(max(score, 0.0), 1.0)

    def _load_system_prompt(self) -> str:
        return PROMPT_PATH.read_text(encoding="utf-8")
