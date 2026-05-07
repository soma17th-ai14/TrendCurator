from app.agents.relevance_filter import SolarMiniRelevanceFilter
from app.core.models import Document


def make_document(**overrides):
    data = {
        "document_id": "doc_001",
        "title": "LangGraph multi-agent workflow benchmark",
        "source": "huggingface",
        "url": "https://example.com/doc",
        "published_at": "2026-05-08",
        "collected_at": "2026-05-08T09:00:00",
        "category": "agent",
        "tags": ["multi-agent", "workflow"],
        "content": "This paper studies tool-use agents with memory and orchestration.",
        "summary": "Agent workflow evaluation.",
        "metadata": {},
    }
    data.update(overrides)
    return Document(**data)


def test_solar_mini_relevance_filter_accepts_agent_document():
    document = make_document()

    decision = SolarMiniRelevanceFilter().evaluate(document)

    assert decision.is_relevant is True
    assert decision.score >= 0.18
    assert "agent" in decision.matched_keywords


def test_solar_mini_relevance_filter_rejects_unrelated_document():
    document = make_document(
        title="Database indexing release notes",
        category="llm",
        tags=[],
        content="A short note about database storage internals.",
        summary="",
    )

    decision = SolarMiniRelevanceFilter().evaluate(document)

    assert decision.is_relevant is False
    assert decision.matched_keywords == []
