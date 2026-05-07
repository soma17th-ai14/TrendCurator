"""Relevance filtering for the collection pipeline."""

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
        """Return the temporary internal response shape for this filter.

        This shape is not part of docs/api-spec.md yet. It should be reviewed
        and adjusted when the relevance filter response contract is finalized.
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
    """Deterministic relevance gate shaped for later Solar Mini replacement.

    The current implementation is intentionally local and dependency-free.
    It preserves the Relevance Filter boundary from docs/api-spec.md while
    allowing the scoring backend to be replaced by an LLM client later.
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
