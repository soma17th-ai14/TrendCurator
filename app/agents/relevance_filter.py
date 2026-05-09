"""수집 파이프라인에서 사용하는 관련성 필터."""

from __future__ import annotations

from dataclasses import dataclass
import re

from app.core.models import NormalizedDocument


DEFAULT_AGENT_KEYWORDS = [
    "agent",
    "agents",
    "ai agent",
    "agentic",
    "multi-agent",
    "multi agent",
    "langgraph",
    "tool-use",
    "tool use",
    "function calling",
    "workflow",
    "orchestration",
    "planner",
    "rag",
    "retrieval",
    "memory",
    "reasoning",
    "benchmark",
]

CORE_AGENT_KEYWORDS = {
    "agent",
    "agents",
    "ai agent",
    "agentic",
    "multi-agent",
    "multi agent",
    "langgraph",
    "tool-use",
    "tool use",
    "function calling",
    "planner",
}


@dataclass(frozen=True)
class RelevanceDecision:
    document: NormalizedDocument
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
            "doc_id": self.document.doc_id,
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
    core_keywords: tuple[str, ...] = tuple(CORE_AGENT_KEYWORDS)
    threshold: float = 0.18

    def evaluate(self, document: NormalizedDocument) -> RelevanceDecision:
        text = document.searchable_text.lower()
        matched = self._matched_keywords(text)
        score = self._score(document=document, matched_keywords=matched)
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

    def filter(self, documents: list[NormalizedDocument]) -> list[RelevanceDecision]:
        return [decision for decision in map(self.evaluate, documents) if decision.is_relevant]

    def _score(self, document: NormalizedDocument, matched_keywords: list[str]) -> float:
        core_count = sum(1 for keyword in matched_keywords if keyword in self.core_keywords)
        context_count = len(matched_keywords) - core_count
        has_core_signal = core_count > 0 or self._category_hint_matches_core(document.category_hint)

        core_score = min(core_count * 0.1, 0.7)
        context_score = min(context_count * 0.04, 0.2)
        category_score = self._category_score(document.category_hint, has_core_signal)
        metadata_score = 0.04 if document.metadata else 0.0
        score = min(core_score + context_score + category_score + metadata_score, 1.0)
        if not has_core_signal:
            return min(score, self.threshold - 0.01)
        return score

    def _contains_keyword(self, text: str, keyword: str) -> bool:
        return bool(self._keyword_spans(text, keyword))

    def _matched_keywords(self, text: str) -> list[str]:
        selected: list[tuple[int, str]] = []
        occupied_spans: list[tuple[int, int]] = []

        for index, keyword in sorted(
            enumerate(self.keywords),
            key=lambda item: (-len(item[1]), item[0]),
        ):
            spans = self._keyword_spans(text, keyword)
            available_span = self._first_non_overlapping_span(spans, occupied_spans)
            if available_span is None:
                continue
            occupied_spans.extend(spans)
            selected.append((index, keyword))

        return [keyword for _, keyword in sorted(selected)]

    def _keyword_spans(self, text: str, keyword: str) -> list[tuple[int, int]]:
        escaped = re.escape(keyword.lower())
        pattern = rf"(?<![a-z0-9]){escaped}(?![a-z0-9])"
        return [match.span() for match in re.finditer(pattern, text)]

    def _first_non_overlapping_span(
        self,
        spans: list[tuple[int, int]],
        occupied_spans: list[tuple[int, int]],
    ) -> tuple[int, int] | None:
        for span in spans:
            if not any(self._overlaps(span, occupied) for occupied in occupied_spans):
                return span
        return None

    def _overlaps(self, first: tuple[int, int], second: tuple[int, int]) -> bool:
        return first[0] < second[1] and second[0] < first[1]

    def _category_hint_matches(self, category_hint: str) -> bool:
        text = category_hint.lower()
        return any(self._contains_keyword(text, keyword) for keyword in self.keywords)

    def _category_hint_matches_core(self, category_hint: str) -> bool:
        text = category_hint.lower()
        return any(self._contains_keyword(text, keyword) for keyword in self.core_keywords)

    def _category_score(self, category_hint: str, has_core_signal: bool) -> float:
        if self._category_hint_matches_core(category_hint):
            return 0.16
        if has_core_signal and self._category_hint_matches(category_hint):
            return 0.08
        return 0.0
