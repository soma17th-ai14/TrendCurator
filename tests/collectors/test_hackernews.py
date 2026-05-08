"""HackerNews 수집기 테스트.

실제 HTTP 호출 없이 fixture와 mocking으로 fetch/normalize 동작을 검증한다.
"""

import json
from datetime import date, datetime
from pathlib import Path

import httpx
import pytest

from app.collectors.base import RawItem
from app.collectors.hackernews import HackerNewsCollector
from app.core.models import Document

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_search_json() -> dict:
    with (FIXTURES_DIR / "hn_search_2026_05_06.json").open(encoding="utf-8") as f:
        return json.load(f)


def test_source_name_is_hackernews():
    assert HackerNewsCollector.source_name == "hackernews"


def test_normalize_story_with_external_url():
    collector = HackerNewsCollector()
    hit = _load_search_json()["hits"][0]
    raw = RawItem(source="hackernews", payload=hit)
    doc = collector.normalize(raw)
    assert isinstance(doc, Document)
    assert doc.document_id == "hackernews_40123456"
    assert doc.title == "Show HN: Open-source multi-agent framework for LLMs"
    assert doc.source == "hackernews"
    assert doc.url == "https://example.com/multi-agent-framework"
    assert doc.published_at == date(2026, 5, 6)
    assert doc.category == "agent"
    assert doc.tags == []
    assert doc.summary == ""
    assert "multi-agent framework" in doc.content
    assert doc.metadata["author"] == "alice"
    assert doc.metadata["score"] == 215
    assert doc.metadata["comments_count"] == 87
    assert doc.metadata["hn_url"] == "https://news.ycombinator.com/item?id=40123456"


def test_normalize_ask_hn_uses_hn_url_when_external_url_missing():
    collector = HackerNewsCollector()
    hit = _load_search_json()["hits"][1]
    raw = RawItem(source="hackernews", payload=hit)
    doc = collector.normalize(raw)
    assert doc.url == "https://news.ycombinator.com/item?id=40123457"
    assert "Ask HN" in doc.title
    assert "multi-agent setups" in doc.content


@pytest.mark.asyncio
async def test_fetch_calls_algolia_search_with_date_range(monkeypatch):
    """fetch는 Algolia search API를 한 번 호출하고 hits를 RawItem으로 변환한다."""

    search_json = _load_search_json()
    captured_urls = []

    async def fake_get(self, url, *args, **kwargs):
        params = kwargs.get("params") or {}
        if params:
            from urllib.parse import urlencode
            full_url = f"{url}?{urlencode(params)}"
        else:
            full_url = url
        captured_urls.append(full_url)
        return httpx.Response(200, json=search_json, request=httpx.Request("GET", full_url))

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    collector = HackerNewsCollector()
    items = await collector.fetch(date(2026, 5, 6))

    assert len(captured_urls) == 1
    url = captured_urls[0]
    assert "hn.algolia.com/api/v1/search" in url
    assert "tags=story" in url
    assert "numericFilters=" in url
    assert "created_at_i%3E" in url or "created_at_i>" in url
    assert "created_at_i%3C" in url or "created_at_i<" in url

    assert len(items) == 2
    assert all(item.source == "hackernews" for item in items)
    assert items[0].payload["objectID"] == "40123456"
    assert items[1].payload["objectID"] == "40123457"
