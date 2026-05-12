"""Groundedness checking and prompt repair helpers.

The checker is intentionally usable without an external judge model. When a
RAGAS evaluator is supplied by the runtime, callers can plug it in; otherwise a
deterministic evidence-overlap score keeps the API and Streamlit demo working.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import re
from typing import Protocol


class RagasEvaluator(Protocol):
    def score(self, *, answer: str, contexts: list[str], question: str | None = None) -> float:
        ...


@dataclass(frozen=True)
class GroundednessCheckRequest:
    answer: str
    contexts: list[str]
    question: str | None = None
    threshold: float = 0.8


@dataclass(frozen=True)
class GroundednessCheckResult:
    score: float
    passed: bool
    threshold: float
    fallback_required: bool
    method: str
    feedback: list[str] = field(default_factory=list)


class GroundednessChecker:
    """Validate that an answer is supported by retrieved source context."""

    def __init__(self, evaluator: RagasEvaluator | None = None) -> None:
        self._evaluator = evaluator

    def check(self, request: GroundednessCheckRequest) -> GroundednessCheckResult:
        if self._evaluator is not None:
            score = _clamp(self._evaluator.score(
                answer=request.answer,
                contexts=request.contexts,
                question=request.question,
            ))
            method = "ragas"
        else:
            score = self._lexical_support_score(request.answer, request.contexts)
            method = "lexical-ragas-fallback"

        passed = score >= request.threshold
        return GroundednessCheckResult(
            score=score,
            passed=passed,
            threshold=request.threshold,
            fallback_required=not passed,
            method=method,
            feedback=self._feedback(score, request.threshold),
        )

    def repair_prompt(self, *, original_prompt: str, result: GroundednessCheckResult) -> str:
        feedback = "\n".join(f"- {item}" for item in result.feedback)
        return (
            f"{original_prompt}\n\n"
            "Groundedness repair instructions:\n"
            "- Use only facts explicitly present in the provided source documents.\n"
            "- If evidence is missing, say that the source does not state it.\n"
            "- Keep citations tied to the source document ids.\n"
            f"{feedback}"
        )

    def _lexical_support_score(self, answer: str, contexts: list[str]) -> float:
        answer_terms = _keywords(answer)
        if not answer_terms:
            return 1.0

        context_terms: set[str] = set()
        for context in contexts:
            context_terms.update(_keywords(context))

        if not context_terms:
            return 0.0

        # 한국어 답변 + 영어 소스 교차언어 케이스: ASCII 기술 용어만 비교
        answer_ascii = {t for t in answer_terms if t.isascii()}
        korean_ratio = 1.0 - (len(answer_ascii) / len(answer_terms))
        if korean_ratio > 0.4 and answer_ascii:
            context_ascii = {t for t in context_terms if t.isascii()}
            supported = answer_ascii & context_ascii
            return round(len(supported) / len(answer_ascii), 4)

        supported = answer_terms & context_terms
        return round(len(supported) / len(answer_terms), 4)

    def _feedback(self, score: float, threshold: float) -> list[str]:
        if score >= threshold:
            return ["Answer is sufficiently supported by the retrieved context."]
        return [
            f"Groundedness score {score:.2f} is below threshold {threshold:.2f}.",
            "Regenerate with fewer unsupported claims and stronger source anchoring.",
        ]


def _keywords(text: str) -> set[str]:
    tokens = re.findall(r"[A-Za-z0-9가-힣]{2,}", text.lower())
    stopwords = {
        "the", "and", "for", "with", "from", "that", "this", "are", "was",
        "were", "있습니다", "합니다", "대한", "관련", "그리고", "또한",
    }
    return {token for token in tokens if token not in stopwords}


def _clamp(value: float) -> float:
    return round(max(0.0, min(1.0, float(value))), 4)
