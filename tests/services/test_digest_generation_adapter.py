from datetime import date

import pytest
from pydantic import ValidationError

from app.core.models import (
    DailyDigestRetrievalResult,
    DigestCandidate,
    DigestItem,
    DigestGenerationRunResult,
    SolarProDigestGenerationResult,
)
from app.services.digest_generation_adapter import DigestGenerationAdapter


def _candidate(document_id: str = "doc_001", **overrides) -> DigestCandidate:
    base = {
        "document_id": document_id,
        "source": "huggingface",
        "title": f"Candidate {document_id}",
        "url": f"https://example.com/{document_id}",
        "published_at": date(2026, 5, 5),
        "content": "Agent workflow content",
        "summary_preview": "Agent workflow summary",
        "similarity_score": 0.87,
        "relevance_score": 0.93,
        "matched_keywords": ["agent"],
        "tags": ["agent"],
        "metadata": {},
    }
    base.update(overrides)
    return DigestCandidate(**base)


def _item(document_id: str = "doc_001", **overrides) -> DigestItem:
    base = {
        "document_id": document_id,
        "title": f"Candidate {document_id}",
        "source": "huggingface",
        "url": f"https://example.com/{document_id}",
        "published_at": date(2026, 5, 5),
        "summary": "핵심 요약",
        "key_points": ["핵심 내용"],
        "contribution": "주요 기여",
        "benchmark": "명시된 근거 없음",
        "critique": "명시된 근거 없음",
        "tags": ["agent"],
        "evidence_document_ids": [document_id],
    }
    base.update(overrides)
    return DigestItem(**base)


def _retrieval_result() -> DailyDigestRetrievalResult:
    candidates = [_candidate("doc_001"), _candidate("doc_002")]
    return DailyDigestRetrievalResult(
        digest_date=date(2026, 5, 6),
        candidates=candidates,
        total_count=5,
        selected_count=2,
    )


def _generation_result(**overrides) -> SolarProDigestGenerationResult:
    base = {
        "digest_id": "digest_20260506",
        "date": date(2026, 5, 6),
        "title": "AI Agent Daily Digest",
        "items": [_item("doc_001"), _item("doc_002")],
        "groundedness_score": 0.91,
    }
    base.update(overrides)
    return SolarProDigestGenerationResult(**base)


def test_adapter_builds_solar_generation_request_from_retrieval_result():
    adapter = DigestGenerationAdapter(language="ko")
    retrieval_result = _retrieval_result()

    request = adapter.to_generation_request(
        retrieval_result,
        profile_keywords=["LangGraph", "RAG"],
    )

    assert request.digest_date == date(2026, 5, 6)
    assert request.language == "ko"
    assert request.profile_keywords == ["LangGraph", "RAG"]
    assert [candidate.document_id for candidate in request.candidates] == ["doc_001", "doc_002"]


def test_adapter_builds_digest_run_result_for_followup_layers():
    adapter = DigestGenerationAdapter()

    result = adapter.to_run_result(
        retrieval_result=_retrieval_result(),
        generation_result=_generation_result(),
    )

    assert result.digest_id == "digest_20260506"
    assert result.status == "completed"
    assert result.item_count == 2
    assert result.candidate_count == 5
    assert result.selected_candidate_count == 2
    assert result.source_document_ids == ["doc_001", "doc_002"]
    assert result.groundedness_score == 0.91
    assert result.digest.items[0].document_id == "doc_001"


def test_adapter_rejects_generation_date_mismatch():
    adapter = DigestGenerationAdapter()

    with pytest.raises(ValueError, match="date"):
        adapter.to_run_result(
            retrieval_result=_retrieval_result(),
            generation_result=_generation_result(date=date(2026, 5, 7)),
        )


def test_adapter_rejects_generation_item_order_mismatch():
    adapter = DigestGenerationAdapter()

    with pytest.raises(ValueError, match="item 순서"):
        adapter.to_run_result(
            retrieval_result=_retrieval_result(),
            generation_result=_generation_result(items=[_item("doc_002"), _item("doc_001")]),
        )


def test_adapter_rejects_unknown_evidence_ids():
    adapter = DigestGenerationAdapter()

    with pytest.raises(ValueError, match="evidence_document_ids"):
        adapter.to_run_result(
            retrieval_result=_retrieval_result(),
            generation_result=_generation_result(
                items=[
                    _item("doc_001", evidence_document_ids=["doc_001", "unknown_doc"]),
                    _item("doc_002"),
                ]
            ),
        )


def test_digest_run_result_validates_count_consistency():
    digest = _generation_result()

    with pytest.raises(ValidationError):
        DigestGenerationRunResult(
            digest_id="digest_20260506",
            date=date(2026, 5, 6),
            item_count=3,
            candidate_count=5,
            selected_candidate_count=2,
            source_document_ids=["doc_001", "doc_002"],
            groundedness_score=0.91,
            digest=digest,
        )
