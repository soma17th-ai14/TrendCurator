"""Document 모델 검증 테스트.

api-spec.md 11장의 필드와 enum을 Pydantic으로 강제하는지 확인한다.
"""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.core.models import Document


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
