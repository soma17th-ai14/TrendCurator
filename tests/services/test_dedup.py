"""문서 중복 제거 모듈 테스트.

URL 정확 일치 + 정규화된 제목 일치 기준의 1차 구현을 검증한다.
"""

from datetime import datetime

from app.core.models import Document
from app.services.dedup import dedup


def _doc(
    *,
    document_id: str = "doc_1",
    title: str = "Sample Title",
    url: str = "https://example.com/1",
    source: str = "huggingface",
) -> Document:
    return Document(
        document_id=document_id,
        title=title,
        source=source,
        url=url,
        collected_at=datetime(2026, 5, 6, 9, 0, 0),
        category="agent",
        tags=[],
        content="",
        summary="",
    )


def test_dedup_empty_list_returns_empty():
    assert dedup([]) == []


def test_dedup_unique_documents_preserved():
    docs = [
        _doc(document_id="a", title="First", url="https://example.com/a"),
        _doc(document_id="b", title="Second", url="https://example.com/b"),
    ]
    result = dedup(docs)
    assert [d.document_id for d in result] == ["a", "b"]


def test_dedup_same_url_keeps_first():
    docs = [
        _doc(document_id="a", title="First", url="https://example.com/x"),
        _doc(document_id="b", title="Second", url="https://example.com/x"),
    ]
    result = dedup(docs)
    assert [d.document_id for d in result] == ["a"]


def test_dedup_normalized_title_collapses_case_and_whitespace():
    """대소문자, 양 끝 공백, 다중 공백 차이는 같은 제목으로 본다."""
    docs = [
        _doc(document_id="a", title="Multi-Agent Survey", url="https://a.example/1"),
        _doc(document_id="b", title="  multi-agent   survey ", url="https://b.example/2"),
    ]
    result = dedup(docs)
    assert [d.document_id for d in result] == ["a"]


def test_dedup_normalized_title_strips_punctuation():
    """문장부호 차이도 같은 제목으로 본다."""
    docs = [
        _doc(document_id="a", title="LangGraph: A Survey!", url="https://a.example/1"),
        _doc(document_id="b", title="langgraph a survey", url="https://b.example/2"),
    ]
    result = dedup(docs)
    assert [d.document_id for d in result] == ["a"]


def test_dedup_different_titles_and_urls_kept():
    docs = [
        _doc(document_id="a", title="Paper One", url="https://example.com/1"),
        _doc(document_id="b", title="Paper Two", url="https://example.com/2"),
        _doc(document_id="c", title="Paper Three", url="https://example.com/3"),
    ]
    result = dedup(docs)
    assert [d.document_id for d in result] == ["a", "b", "c"]


def test_dedup_preserves_input_order():
    docs = [
        _doc(document_id="z", title="Z paper", url="https://example.com/z"),
        _doc(document_id="a", title="A paper", url="https://example.com/a"),
        _doc(document_id="m", title="M paper", url="https://example.com/m"),
    ]
    result = dedup(docs)
    assert [d.document_id for d in result] == ["z", "a", "m"]


def test_dedup_does_not_collide_titles_that_normalize_to_empty():
    """비-라틴(예: 한국어) 제목이 정규화되어 빈 문자열이 되더라도 서로 다른 문서로 본다."""
    docs = [
        _doc(document_id="a", title="멀티 에이전트 서베이", url="https://a.example/1"),
        _doc(document_id="b", title="롱 컨텍스트 메모리", url="https://b.example/2"),
    ]
    result = dedup(docs)
    assert [d.document_id for d in result] == ["a", "b"]
