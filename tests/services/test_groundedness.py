from app.services.groundedness import GroundednessChecker, GroundednessCheckRequest


def test_groundedness_passes_when_answer_terms_are_supported():
    checker = GroundednessChecker()
    result = checker.check(GroundednessCheckRequest(
        answer="LangGraph supports multi-agent workflow orchestration.",
        contexts=["LangGraph is used for multi-agent workflow orchestration."],
        threshold=0.6,
    ))

    assert result.passed is True
    assert result.score >= 0.6


def test_groundedness_fails_without_context_support():
    checker = GroundednessChecker()
    result = checker.check(GroundednessCheckRequest(
        answer="LangGraph provides benchmark results.",
        contexts=["This paper discusses retrieval augmented generation."],
        threshold=0.8,
    ))

    assert result.passed is False
    assert result.fallback_required is True
