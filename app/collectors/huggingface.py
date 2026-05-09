"""HuggingFace Daily Papers 수집기.

두 단계로 동작:
1. https://huggingface.co/papers?date=YYYY-MM-DD HTML을 가져와 arxiv ID 목록을 추출.
2. https://huggingface.co/api/papers/{arxiv_id} JSON을 병렬로 호출하여 상세 메타데이터를 받음.

각 paper 메타데이터는 normalize()에서 공통 Document로 변환된다.
내부용 summary, category, tags는 후속 메타데이터 추출 agent가 채우므로 여기서는 비워둔다.
"""

import asyncio
import re
from datetime import date, datetime
from typing import ClassVar

import httpx
from bs4 import BeautifulSoup

from app.collectors.base import BaseCollector, RawItem
from app.core.models import Document

DAILY_URL_TEMPLATE = "https://huggingface.co/papers?date={date}"
PAPER_API_TEMPLATE = "https://huggingface.co/api/papers/{arxiv_id}"
ARXIV_ID_PATTERN = re.compile(r"^/papers/(\d{4}\.\d{4,5})$")
HTTP_TIMEOUT = httpx.Timeout(10.0, connect=5.0)


class HuggingFaceDailyPapersCollector(BaseCollector):
    source_name: ClassVar[str] = "huggingface"

    async def fetch(self, target_date: date) -> list[RawItem]:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT) as client:
            daily_url = DAILY_URL_TEMPLATE.format(date=target_date.isoformat())
            daily_response = await client.get(daily_url)
            daily_response.raise_for_status()

            arxiv_ids = self._extract_arxiv_ids(daily_response.text)

            tasks = [
                client.get(PAPER_API_TEMPLATE.format(arxiv_id=arxiv_id))
                for arxiv_id in arxiv_ids
            ]
            responses = await asyncio.gather(*tasks)

        items: list[RawItem] = []
        for response in responses:
            response.raise_for_status()
            items.append(RawItem(source="huggingface", payload=response.json()))
        return items

    def _extract_arxiv_ids(self, html: str) -> list[str]:
        soup = BeautifulSoup(html, "html.parser")
        ids: list[str] = []
        seen: set[str] = set()
        for anchor in soup.find_all("a", href=True):
            match = ARXIV_ID_PATTERN.match(anchor["href"])
            if match:
                arxiv_id = match.group(1)
                if arxiv_id not in seen:
                    seen.add(arxiv_id)
                    ids.append(arxiv_id)
        return ids

    def normalize(self, item: RawItem) -> Document:
        payload = item.payload
        arxiv_id = payload["id"]
        published_str = payload.get("publishedAt")
        published = (
            datetime.fromisoformat(published_str.replace("Z", "+00:00")).date()
            if published_str
            else None
        )
        authors = [a.get("name", "") for a in payload.get("authors", [])]

        metadata = {
            "authors": authors,
            "upvotes": payload.get("upvotes"),
            "discussion_id": payload.get("discussionId"),
        }
        metadata = {k: v for k, v in metadata.items() if v is not None}

        return Document(
            document_id=f"huggingface_{arxiv_id}",
            title=payload["title"],
            source="huggingface",
            url=f"https://huggingface.co/papers/{arxiv_id}",
            published_at=published,
            collected_at=datetime.now(),
            category="agent",
            tags=[],
            content=payload.get("summary", ""),
            summary="",
            metadata=metadata,
        )
