"""내부용 메타데이터 추출 agent.

문서의 `title`/`content`를 프롬프트에 삽입하여 LLM에 1회 호출하고,
응답 JSON에서 `summary`, `category`, `tags`를 추출하여 Document를 갱신한다.

본 모듈은 LLM 호출의 책임만 가진다. LLM 호출 자체는 `LLMClient` Protocol로 추상화되어
실제 Adapter(OpenAI/Anthropic/Ollama 등)는 별도 모듈에서 주입된다.
"""

import json
import re
from typing import get_args

from app.core.llm_client import LLMClient
from app.core.models import Category, Document

_VALID_CATEGORIES: tuple[str, ...] = get_args(Category)
_DEFAULT_CATEGORY: str = "agent"
_TAG_NORMALIZE_RE = re.compile(r"[\s_]+")
_TAG_STRIP_RE = re.compile(r"[^a-z0-9-]")


def _normalize_tag(tag: str) -> str:
    lowered = tag.strip().lower()
    hyphenated = _TAG_NORMALIZE_RE.sub("-", lowered)
    cleaned = _TAG_STRIP_RE.sub("", hyphenated)
    return cleaned.strip("-")


class MetadataExtractor:
    def __init__(self, llm_client: LLMClient, prompt_template: str):
        self._llm_client = llm_client
        self._prompt_template = prompt_template

    async def enrich(self, document: Document) -> Document:
        prompt = self._prompt_template.format(
            title=document.title,
            content=document.content,
        )
        raw_response = await self._llm_client.complete(prompt)

        try:
            parsed = json.loads(raw_response)
        except json.JSONDecodeError as e:
            raise ValueError(f"LLM 응답이 JSON으로 파싱되지 않습니다: {e}") from e

        summary = str(parsed.get("summary", ""))
        category = parsed.get("category", _DEFAULT_CATEGORY)
        if category not in _VALID_CATEGORIES:
            category = _DEFAULT_CATEGORY

        raw_tags = parsed.get("tags") or []
        tags = [t for t in (_normalize_tag(str(tag)) for tag in raw_tags) if t]

        return document.model_copy(
            update={
                "summary": summary,
                "category": category,
                "tags": tags,
            }
        )
