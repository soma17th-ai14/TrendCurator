"""Solar Mini backed relevance filtering."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from app.agents.relevance_filter import RelevanceDecision, SolarMiniRelevanceFilter
from app.core.models import Document
from app.core.settings import SolarSettings
from app.core.solar_client import SolarClient, SolarMessage


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
    """Relevance filter that delegates judgment to Solar Mini."""

    client: SolarJsonClient
    settings: SolarSettings
    fallback_filter: SolarMiniRelevanceFilter = SolarMiniRelevanceFilter()

    @classmethod
    def from_settings(cls, settings: SolarSettings) -> "SolarMiniLLMRelevanceFilter":
        return cls(client=SolarClient(settings), settings=settings)

    def evaluate(self, document: Document) -> RelevanceDecision:
        result = self.client.chat_json(
            model=self.settings.mini_model,
            messages=[
                SolarMessage(
                    role="system",
                    content=(
                        "AI Agent Daily Digest 후보 관련성을 판정합니다. "
                        "반드시 JSON만 반환합니다."
                    ),
                ),
                SolarMessage(role="user", content=self._format_document(document)),
            ],
            temperature=0.0,
        )

        fallback = self.fallback_filter.evaluate(document)
        score = float(result.get("score", fallback.score))
        matched_keywords = result.get("matched_keywords", fallback.matched_keywords)
        if not isinstance(matched_keywords, list):
            matched_keywords = fallback.matched_keywords

        return RelevanceDecision(
            document=document,
            is_relevant=bool(result.get("is_relevant", fallback.is_relevant)),
            score=round(score, 4),
            matched_keywords=[str(keyword) for keyword in matched_keywords],
            reason=str(result.get("reason", fallback.reason)),
        )

    def filter(self, documents: list[Document]) -> list[RelevanceDecision]:
        return [decision for decision in map(self.evaluate, documents) if decision.is_relevant]

    def _format_document(self, document: Document) -> str:
        return (
            f"title: {document.title}\n"
            f"source: {document.source}\n"
            f"published_at: {document.published_at}\n"
            f"category: {document.category}\n"
            f"tags: {', '.join(document.tags)}\n"
            f"summary: {document.summary}\n"
            f"content:\n{document.content}"
        )
