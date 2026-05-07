from app.agents.relevance_filter import SolarMiniRelevanceFilter
from app.core.models import NormalizedDocument


def make_document(**overrides):
    data = {
        "doc_id": "doc_001",
        "title": "LangGraph multi-agent workflow benchmark",
        "source": "huggingface",
        "url": "https://example.com/doc",
        "published_date": "2026-05-08",
        "raw_text": "This paper studies tool-use agents with memory and orchestration.",
        "category_hint": "multi-agent workflow",
        "external_id": "doc_001",
        "content_hash": "hash_doc_001",
        "metadata": {"authors": ["Author A"]},
    }
    data.update(overrides)
    return NormalizedDocument(**data)


def test_solar_mini_relevance_filter_accepts_agent_document():
    document = make_document()

    decision = SolarMiniRelevanceFilter().evaluate(document)

    assert decision.is_relevant is True
    assert decision.score >= 0.18
    assert "agent" in decision.matched_keywords
    assert decision.to_response() == {
        "doc_id": "doc_001",
        "is_relevant": True,
        "score": decision.score,
        "matched_keywords": decision.matched_keywords,
        "reason": decision.reason,
    }


def test_solar_mini_relevance_filter_rejects_unrelated_document():
    document = make_document(
        title="Database indexing release notes",
        category_hint="database",
        raw_text="A short note about database storage internals.",
        metadata={},
    )

    decision = SolarMiniRelevanceFilter().evaluate(document)

    assert decision.is_relevant is False
    assert decision.matched_keywords == []
