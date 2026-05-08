"""HuggingFace Daily Papers 수집기 테스트.

실제 HTTP 호출 없이 fixture와 mocking으로 fetch/normalize 동작을 검증한다.
"""

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.collectors.base import RawItem
from app.collectors.huggingface import HuggingFaceDailyPapersCollector
from app.core.models import Document

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_html() -> str:
    return (FIXTURES_DIR / "hf_daily_papers_2026_05_06.html").read_text(encoding="utf-8")


def _load_paper_json() -> dict:
    with (FIXTURES_DIR / "hf_paper_2405_01234.json").open(encoding="utf-8") as f:
        return json.load(f)


def test_source_name_is_huggingface():
    assert HuggingFaceDailyPapersCollector.source_name == "huggingface"


def test_extract_arxiv_ids_from_html():
    collector = HuggingFaceDailyPapersCollector()
    ids = collector._extract_arxiv_ids(_load_html())
    assert ids == ["2405.01234", "2405.05678"]


def test_normalize_converts_hf_payload_to_document():
    collector = HuggingFaceDailyPapersCollector()
    raw = RawItem(source="huggingface", payload=_load_paper_json())
    doc = collector.normalize(raw)
    assert isinstance(doc, Document)
    assert doc.document_id == "huggingface_2405.01234"
    assert doc.title == "Multi-Agent Orchestration Survey"
    assert doc.source == "huggingface"
    assert doc.url == "https://huggingface.co/papers/2405.01234"
    assert doc.published_at == date(2026, 5, 5)
    assert doc.category == "agent"  # 기본 카테고리 (메타데이터 추출 단계에서 LLM이 재분류)
    assert doc.tags == []
    assert doc.summary == ""  # 내부용 요약은 메타데이터 추출 단계에서 채움
    assert "Multi-Agent Orchestration Survey" in doc.content or "survey" in doc.content.lower()
    assert doc.metadata["upvotes"] == 42
    assert doc.metadata["authors"] == ["Alice", "Bob"]


def test_normalize_handles_missing_optional_fields():
    collector = HuggingFaceDailyPapersCollector()
    minimal_payload = {
        "id": "2405.99999",
        "title": "Minimal Paper",
        "summary": "Body",
        "authors": [],
        "publishedAt": "2026-05-01T00:00:00Z",
    }
    raw = RawItem(source="huggingface", payload=minimal_payload)
    doc = collector.normalize(raw)
    assert doc.document_id == "huggingface_2405.99999"
    assert doc.metadata.get("upvotes") is None or doc.metadata["upvotes"] == 0


@pytest.mark.asyncio
async def test_fetch_calls_daily_page_then_paper_api(monkeypatch):
    """fetch는 daily 페이지를 한 번 호출하고, 추출된 각 arxiv_id마다 paper API를 호출한다."""

    daily_html = _load_html()
    paper_json = _load_paper_json()

    call_log = []

    async def fake_get(self, url, *args, **kwargs):
        call_log.append(url)
        if "papers?date=" in url:
            return httpx.Response(200, text=daily_html, request=httpx.Request("GET", url))
        if "/api/papers/2405.01234" in url:
            return httpx.Response(200, json=paper_json, request=httpx.Request("GET", url))
        if "/api/papers/2405.05678" in url:
            other = dict(paper_json)
            other["id"] = "2405.05678"
            other["title"] = "Long-context Memory Agents"
            return httpx.Response(200, json=other, request=httpx.Request("GET", url))
        raise AssertionError(f"unexpected URL: {url}")

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = HuggingFaceDailyPapersCollector()
    items = await collector.fetch(date(2026, 5, 6))

    assert len(items) == 2
    assert all(item.source == "huggingface" for item in items)
    daily_calls = [u for u in call_log if "papers?date=" in u]
    paper_calls = [u for u in call_log if "/api/papers/" in u]
    assert len(daily_calls) == 1
    assert len(paper_calls) == 2
