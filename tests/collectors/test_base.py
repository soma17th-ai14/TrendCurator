"""BaseCollector 인터페이스 테스트.

추상 메서드 강제 + 더미 서브클래스로 fetch/normalize 동작을 검증한다.
"""

from datetime import date, datetime

import pytest
from pydantic import ValidationError

from app.collectors.base import BaseCollector, RawItem
from app.core.models import Document


def test_base_collector_cannot_be_instantiated():
    with pytest.raises(TypeError):
        BaseCollector()  # type: ignore[abstract]


class FakeCollector(BaseCollector):
    source_name = "huggingface"

    async def fetch(self, target_date: date) -> list[RawItem]:
        return [
            RawItem(
                source="huggingface",
                payload={"id": "1", "title": "Sample Paper", "url": "https://example.com/1"},
            )
        ]

    def normalize(self, item: RawItem) -> Document:
        return Document(
            document_id=f"huggingface_{item.payload['id']}",
            title=item.payload["title"],
            source="huggingface",
            url=item.payload["url"],
            collected_at=datetime(2026, 5, 6, 9, 0, 0),
            category="agent",
            tags=[],
            content="",
            summary="",
        )


@pytest.mark.asyncio
async def test_fake_collector_fetch_returns_raw_items():
    collector = FakeCollector()
    items = await collector.fetch(date(2026, 5, 6))
    assert len(items) == 1
    assert items[0].source == "huggingface"
    assert items[0].payload["title"] == "Sample Paper"


def test_fake_collector_normalize_returns_document():
    collector = FakeCollector()
    raw = RawItem(
        source="huggingface",
        payload={"id": "42", "title": "Another", "url": "https://example.com/42"},
    )
    doc = collector.normalize(raw)
    assert isinstance(doc, Document)
    assert doc.document_id == "huggingface_42"
    assert doc.title == "Another"
    assert doc.source == "huggingface"


def test_raw_item_rejects_invalid_source():
    with pytest.raises(ValidationError):
        RawItem(source="reddit", payload={})  # type: ignore[arg-type]
