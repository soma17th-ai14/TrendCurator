import json
from pathlib import Path

from app.agents.relevance_filter import SolarMiniRelevanceFilter
from app.core.models import NormalizedDocument


SAMPLES_PATH = Path(__file__).resolve().parents[1] / "data" / "samples" / "relevance_eval_documents.json"


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
    assert "multi-agent" in decision.matched_keywords
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


def test_solar_mini_relevance_filter_rejects_general_rag_without_agent_context():
    document = make_document(
        title="RAG evaluation for legal question answering",
        category_hint="rag retrieval evaluation",
        raw_text="This paper compares retrieval quality and answer faithfulness for legal QA datasets.",
        metadata={"authors": ["Author A"]},
    )

    decision = SolarMiniRelevanceFilter().evaluate(document)

    assert decision.is_relevant is False
    assert "rag" in decision.matched_keywords


def test_solar_mini_relevance_filter_accepts_agentic_rag_boundary_document():
    document = make_document(
        title="Agentic RAG controller for research assistants",
        category_hint="agentic-rag retrieval memory",
        raw_text=(
            "The system plans iterative retrieval steps, stores memory, and calls tools "
            "while an agent decides the next action."
        ),
    )

    decision = SolarMiniRelevanceFilter().evaluate(document)

    assert decision.is_relevant is True
    assert "agentic" in decision.matched_keywords
    assert "rag" in decision.matched_keywords


def test_solar_mini_relevance_filter_rejects_general_workflow_orchestration():
    document = make_document(
        title="Enterprise workflow orchestration for data operations",
        category_hint="workflow orchestration data-engineering",
        raw_text="The platform schedules data jobs and coordinates approval workflows across business teams.",
        metadata={"authors": ["Author A"]},
    )

    decision = SolarMiniRelevanceFilter().evaluate(document)

    assert decision.is_relevant is False
    assert "workflow" in decision.matched_keywords


def test_solar_mini_relevance_filter_allows_custom_core_keywords():
    document = make_document(
        title="Autonomous browser operator benchmark",
        category_hint="browser operator",
        raw_text="The benchmark evaluates autonomous browser operators on long-horizon web tasks.",
        metadata={},
    )
    relevance_filter = SolarMiniRelevanceFilter(
        keywords=("browser operator",),
        core_keywords=("browser operator",),
    )

    decision = relevance_filter.evaluate(document)

    assert decision.is_relevant is True
    assert decision.matched_keywords == ["browser operator"]


def test_solar_mini_relevance_filter_prefers_longer_overlapping_keywords():
    document = make_document(
        title="Multi-agent benchmark",
        category_hint="multi-agent",
        raw_text="A benchmark for multi-agent systems.",
        metadata={},
    )

    decision = SolarMiniRelevanceFilter().evaluate(document)

    assert "multi-agent" in decision.matched_keywords
    assert "agent" not in decision.matched_keywords


def test_solar_mini_relevance_filter_matches_labeled_sample_data():
    samples = json.loads(SAMPLES_PATH.read_text(encoding="utf-8"))
    relevance_filter = SolarMiniRelevanceFilter()

    mismatches = []
    for sample in samples:
        document = NormalizedDocument(**sample["document"])
        decision = relevance_filter.evaluate(document)
        expected = sample["expected_is_relevant"]
        assert isinstance(expected, bool)
        if decision.is_relevant != expected:
            mismatches.append(
                {
                    "doc_id": document.doc_id,
                    "expected": expected,
                    "actual": decision.is_relevant,
                    "score": decision.score,
                    "matched_keywords": decision.matched_keywords,
                }
            )

    assert mismatches == []
