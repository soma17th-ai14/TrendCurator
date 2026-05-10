"""Document 모델 검증 테스트.

api-spec.md 11장의 필드와 enum을 Pydantic으로 강제하는지 확인한다.
"""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.core.models import (
    DailyDigestRetrievalRequest,
    DailyDigestRetrievalResult,
    DigestCandidate,
    DigestItem,
    Document,
    SolarProDigestGenerationRequest,
    SolarProDigestGenerationResult,
)


def _valid_payload(**overrides) -> dict:
    base = {
        "document_id": "huggingface_abc123",
        "title": "Multi-Agent Orchestration Survey",
        "source": "huggingface",
        "url": "https://huggingface.co/papers/2405.01234",
        "collected_at": datetime(2026, 5, 6, 9, 0, 0),
        "category": "agent",
        "tags": ["multi-agent", "survey"],
        "content": "본문 전체 텍스트",
        "summary": "멀티 에이전트 관련 서베이 논문이다.",
    }
    base.update(overrides)
    return base


def test_document_minimum_fields_ok():
    doc = Document(**_valid_payload())
    assert doc.source == "huggingface"
    assert doc.category == "agent"
    assert doc.published_at is None
    assert doc.metadata == {}


def test_document_with_published_at_and_metadata():
    doc = Document(
        **_valid_payload(
            published_at=date(2026, 5, 5),
            metadata={"author": "John", "score": 42},
        )
    )
    assert doc.published_at == date(2026, 5, 5)
    assert doc.metadata["score"] == 42


def test_document_invalid_source_rejected():
    with pytest.raises(ValidationError):
        Document(**_valid_payload(source="reddit"))


def test_document_invalid_category_rejected():
    with pytest.raises(ValidationError):
        Document(**_valid_payload(category="other"))


def test_document_required_fields_missing():
    payload = _valid_payload()
    del payload["title"]
    with pytest.raises(ValidationError):
        Document(**payload)


def _candidate_payload(**overrides) -> dict:
    base = {
        "document_id": "doc_001",
        "source": "huggingface",
        "title": "Example Daily Paper",
        "url": "https://huggingface.co/papers/2405.01234",
        "published_at": date(2026, 5, 5),
        "content": "Paper content",
        "summary_preview": "Short summary",
        "similarity_score": 0.87,
        "relevance_score": 0.93,
        "matched_keywords": ["langgraph", "multi-agent"],
        "tags": ["multi-agent", "rag"],
        "metadata": {"external_id": "2405.01234"},
    }
    base.update(overrides)
    return base


def test_digest_candidate_matches_digest_retrieval_contract():
    candidate = DigestCandidate(**_candidate_payload())

    assert candidate.source == "huggingface"
    assert candidate.published_at == date(2026, 5, 5)
    assert candidate.similarity_score == 0.87
    assert candidate.relevance_score == 0.93
    assert candidate.matched_keywords == ["langgraph", "multi-agent"]


def test_digest_candidate_rejects_invalid_scores():
    with pytest.raises(ValidationError):
        DigestCandidate(**_candidate_payload(similarity_score=1.1))

    with pytest.raises(ValidationError):
        DigestCandidate(**_candidate_payload(relevance_score=-0.01))


def test_daily_digest_retrieval_request_defaults_and_constraints():
    request = DailyDigestRetrievalRequest(digest_date=date(2026, 5, 6))

    assert request.lookback_days == 1
    assert request.top_k == 10
    assert request.profile_based is True
    assert request.min_relevance_score == 0.18

    with pytest.raises(ValidationError):
        DailyDigestRetrievalRequest(digest_date=date(2026, 5, 6), top_k=0)


def test_daily_digest_retrieval_result_validates_counts():
    candidate = DigestCandidate(**_candidate_payload())
    result = DailyDigestRetrievalResult(
        digest_date=date(2026, 5, 6),
        candidates=[candidate],
        total_count=31,
        selected_count=1,
    )

    assert result.selected_count == 1

    with pytest.raises(ValidationError):
        DailyDigestRetrievalResult(
            digest_date=date(2026, 5, 6),
            candidates=[candidate],
            total_count=31,
            selected_count=2,
        )

    with pytest.raises(ValidationError):
        DailyDigestRetrievalResult(
            digest_date=date(2026, 5, 6),
            candidates=[candidate],
            total_count=0,
            selected_count=0,
        )


def test_digest_item_matches_public_digest_contract():
    item = DigestItem(
        document_id="doc_001",
        title="Example Daily Paper",
        source="huggingface",
        url="https://huggingface.co/papers/2405.01234",
        published_at=date(2026, 5, 5),
        summary="Core summary",
        key_points=["Point 1", "Point 2"],
        contribution="Main contribution",
        benchmark="Benchmark result",
        critique="Limitations",
        tags=["multi-agent"],
        evidence_document_ids=["doc_001"],
    )

    assert item.llm_model == "solar-pro-3"
    assert item.evidence_document_ids == ["doc_001"]


def test_solar_pro_digest_generation_contracts():
    candidate = DigestCandidate(**_candidate_payload())
    request = SolarProDigestGenerationRequest(
        digest_date=date(2026, 5, 6),
        profile_keywords=["LangGraph", "RAG"],
        candidates=[candidate],
    )
    item = DigestItem(
        document_id="doc_001",
        title="Example Daily Paper",
        source="huggingface",
        url="https://huggingface.co/papers/2405.01234",
        published_at=date(2026, 5, 5),
        summary="Core summary",
        key_points=["Point 1"],
        contribution="Main contribution",
        benchmark="Benchmark result",
        critique="Limitations",
        tags=["multi-agent"],
        evidence_document_ids=["doc_001"],
    )
    result = SolarProDigestGenerationResult(
        digest_id="digest_20260506",
        date=date(2026, 5, 6),
        title="AI Agent Daily Digest",
        items=[item],
        groundedness_score=0.91,
    )

    assert request.language == "ko"
    assert request.candidates[0].document_id == "doc_001"
    assert result.items[0].summary == "Core summary"

    with pytest.raises(ValidationError):
        SolarProDigestGenerationResult(
            digest_id="digest_20260506",
            date=date(2026, 5, 6),
            title="AI Agent Daily Digest",
            items=[item],
            groundedness_score=1.2,
        )
