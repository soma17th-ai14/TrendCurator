"""HackerNews 수집기.

Algolia HN Search API(https://hn.algolia.com/api/v1/search)를 사용해 주어진 날짜의
front-page 스토리를 단일 호출로 가져온다.

normalize()는 Algolia hit JSON을 공통 Document로 변환한다. 외부 URL이 없는
Ask HN 같은 스토리는 HN 토론 페이지 URL을 fallback으로 사용한다.

내부용 summary/category/tags는 후속 메타데이터 추출 agent가 채우므로
여기서는 비워둔다.
"""

from datetime import date, datetime, time, timezone
from typing import ClassVar

import httpx

from app.collectors.base import BaseCollector, RawItem
from app.core.models import Document

SEARCH_URL = "https://hn.algolia.com/api/v1/search"
HN_ITEM_URL_TEMPLATE = "https://news.ycombinator.com/item?id={story_id}"
MIN_POINTS = 20
HITS_PER_PAGE = 50
HTTP_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class HackerNewsCollector(BaseCollector):
    source_name: ClassVar[str] = "hackernews"

    async def fetch(self, target_date: date) -> list[RawItem]:
        start = int(datetime.combine(target_date, time.min, tzinfo=timezone.utc).timestamp())
        end = start + 24 * 60 * 60

        params = {
            "tags": "story",
            "numericFilters": f"created_at_i>{start},created_at_i<{end},points>{MIN_POINTS}",
            "hitsPerPage": str(HITS_PER_PAGE),
        }

        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            response = await client.get(SEARCH_URL, params=params)
        response.raise_for_status()

        hits = response.json().get("hits", [])
        return [RawItem(source="hackernews", payload=hit) for hit in hits]

    def normalize(self, item: RawItem) -> Document:
        payload = item.payload
        story_id = payload["objectID"]
        title = payload["title"]
        external_url = payload.get("url")
        hn_url = HN_ITEM_URL_TEMPLATE.format(story_id=story_id)

        published_str = payload.get("created_at")
        published = (
            datetime.fromisoformat(published_str.replace("Z", "+00:00")).date()
            if published_str
            else None
        )

        story_text = payload.get("story_text") or ""
        content = f"{title}\n\n{story_text}".strip() if story_text else title

        metadata = {
            "author": payload.get("author"),
            "score": payload.get("points"),
            "comments_count": payload.get("num_comments"),
            "hn_url": hn_url,
        }
        metadata = {k: v for k, v in metadata.items() if v is not None}

        return Document(
            document_id=f"hackernews_{story_id}",
            title=title,
            source="hackernews",
            url=external_url or hn_url,
            published_at=published,
            collected_at=datetime.now(),
            category="agent",
            tags=[],
            content=content,
            summary="",
            metadata=metadata,
        )
