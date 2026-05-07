"""수집 파이프라인에서 사용하는 관련성 필터."""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.core.models import Document


DEFAULT_AGENT_KEYWORDS = [
    "agent",
    "agents",
    "ai agent",
    "multi-agent",
    "multi agent",
    "langgraph",
    "rag",
    "retrieval",
    "tool-use",
    "tool use",
    "function calling",
    "workflow",
    "orchestration",
    "memory",
    "planner",
    "reasoning",
]


@dataclass(frozen=True)
class RelevanceDecision:
    document: Document
    is_relevant: bool
    score: float
    matched_keywords: list[str]
    reason: str

    def to_response(self) -> dict:
        """관련성 필터의 임시 내부 응답 형식을 반환합니다.

        이 형식은 아직 docs/api-spec.md에 확정된 계약이 아닙니다.
        관련성 필터 응답 계약이 확정되면 함께 검토하고 조정해야 합니다.
        """

        return {
            "document_id": self.document.document_id,
            "is_relevant": self.is_relevant,
            "score": self.score,
            "matched_keywords": self.matched_keywords,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class SolarMiniRelevanceFilter:
    """Solar Mini 호출 실패나 테스트에서 사용할 결정적 관련성 필터입니다.

    현재 구현은 외부 의존성이 없는 로컬 점수 계산 방식입니다.
    docs/api-spec.md의 Relevance Filter 경계를 유지하면서,
    실제 운영에서는 Solar Mini 기반 필터로 교체할 수 있게 분리했습니다.
    """

    keywords: tuple[str, ...] = tuple(DEFAULT_AGENT_KEYWORDS)
    threshold: float = 0.18

    def evaluate(self, document: Document) -> RelevanceDecision:
        text = document.searchable_text.lower()
        matched = [keyword for keyword in self.keywords if self._contains_keyword(text, keyword)]
        score = self._score(document=document, matched_count=len(matched))
        is_relevant = score >= self.threshold
        reason = (
            "AI Agent 관련 키워드와 카테고리 신호가 기준을 충족했습니다."
            if is_relevant
            else "AI Agent 관련 신호가 기준보다 약합니다."
        )
        return RelevanceDecision(
            document=document,
            is_relevant=is_relevant,
            score=round(score, 4),
            matched_keywords=matched,
            reason=reason,
        )

    def filter(self, documents: list[Document]) -> list[RelevanceDecision]:
        return [decision for decision in map(self.evaluate, documents) if decision.is_relevant]

    def _score(self, document: Document, matched_count: int) -> float:
        keyword_score = min(matched_count * 0.08, 0.72)
        category_score = 0.18 if document.category in {"agent", "rag", "framework"} else 0.0
        tag_score = min(len(document.tags) * 0.02, 0.1)
        summary_score = 0.08 if document.summary else 0.0
        return min(keyword_score + category_score + tag_score + summary_score, 1.0)

    def _contains_keyword(self, text: str, keyword: str) -> bool:
        escaped = re.escape(keyword.lower())
        pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
        return re.search(pattern, text) is not None
