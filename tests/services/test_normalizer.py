from datetime import date, datetime

from app.core.models import Document, NormalizedDocument
from app.services.normalizer import normalize_document, normalize_documents


def make_document(**overrides) -> Document:
    data = {
        "document_id": "huggingface_2405.01234",
        "title": "Multi-Agent Orchestration Survey",
        "source": "huggingface",
        "url": "https://huggingface.co/papers/2405.01234",
        "published_at": date(2026, 5, 5),
        "collected_at": datetime(2026, 5, 6, 9, 0, 0),
        "category": "agent",
        "tags": ["multi-agent", "workflow"],
        "content": "본문 전체 텍스트",
        "summary": "멀티 에이전트 관련 서베이 논문이다.",
        "metadata": {"authors": ["Alice", "Bob"], "external_id": "2405.01234"},
    }
    data.update(overrides)
    return Document(**data)


def test_normalize_document_maps_document_contract_to_internal_contract():
    document = make_document()

    normalized = normalize_document(document)

    assert isinstance(normalized, NormalizedDocument)
    assert normalized.doc_id == "huggingface_2405.01234"
    assert normalized.source == "huggingface"
    assert normalized.title == document.title
    assert normalized.url == document.url
    assert normalized.published_date == "2026-05-05"
    assert normalized.raw_text == "멀티 에이전트 관련 서베이 논문이다.\n\n본문 전체 텍스트"
    assert normalized.category_hint == "agent multi-agent workflow"
    assert normalized.external_id == "2405.01234"
    assert len(normalized.content_hash) == 64
    assert normalized.metadata == document.metadata


def test_normalize_document_uses_collected_date_when_published_at_missing():
    document = make_document(published_at=None)

    normalized = normalize_document(document)

    assert normalized.published_date == "2026-05-06"


def test_normalize_document_falls_back_to_document_id_for_external_id():
    document = make_document(metadata={"authors": ["Alice"]})

    normalized = normalize_document(document)

    assert normalized.external_id == document.document_id


def test_normalize_document_deep_copies_metadata():
    authors = ["Alice", "Bob"]
    document = make_document(metadata={"authors": authors, "external_id": "2405.01234"})

    normalized = normalize_document(document)
    authors.append("Carol")

    assert normalized.metadata["authors"] == ["Alice", "Bob"]


def test_normalize_document_content_hash_is_stable_for_same_content():
    first = normalize_document(make_document())
    second = normalize_document(make_document())

    assert first.content_hash == second.content_hash


def test_normalize_document_content_hash_changes_when_content_changes():
    first = normalize_document(make_document())
    second = normalize_document(make_document(content="다른 본문"))

    assert first.content_hash != second.content_hash


def test_normalize_documents_preserves_input_order():
    first = make_document(document_id="doc_1", url="https://example.com/1")
    second = make_document(document_id="doc_2", url="https://example.com/2")

    normalized = normalize_documents([first, second])

    assert [doc.doc_id for doc in normalized] == ["doc_1", "doc_2"]
