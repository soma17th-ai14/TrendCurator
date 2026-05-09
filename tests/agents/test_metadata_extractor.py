"""MetadataExtractor 테스트.

FakeLLMClient를 주입하여 LLM 응답에 따른 Document 갱신 동작을 검증한다.
"""

import json
from datetime import datetime

import pytest

from app.agents.metadata_extractor import MetadataExtractor
from app.core.models import Document


class FakeLLMClient:
    def __init__(self, response: str):
        self.response = response
        self.calls: list[str] = []

    async def complete(self, prompt: str) -> str:
        self.calls.append(prompt)
        return self.response


def _doc(**overrides) -> Document:
    base = {
        "document_id": "huggingface_test",
        "title": "Multi-Agent Orchestration Survey",
        "source": "huggingface",
        "url": "https://huggingface.co/papers/2405.01234",
        "collected_at": datetime(2026, 5, 6, 9, 0, 0),
        "category": "agent",
        "tags": [],
        "content": "본문 내용...",
        "summary": "",
        "metadata": {},
    }
    base.update(overrides)
    return Document(**base)


@pytest.mark.asyncio
async def test_enrich_fills_summary_category_tags_from_llm_response():
    response_json = json.dumps(
        {
            "summary": "멀티 에이전트 오케스트레이션 관련 서베이 논문이다. 여러 LLM 기반 에이전트의 협업 패턴을 정리한다.",
            "category": "agent",
            "tags": ["multi-agent", "survey", "orchestration"],
        }
    )
    extractor = MetadataExtractor(
        llm_client=FakeLLMClient(response=response_json),
        prompt_template="제목: {title}\n본문: {content}",
    )

    enriched = await extractor.enrich(_doc())

    assert "멀티 에이전트" in enriched.summary
    assert enriched.category == "agent"
    assert enriched.tags == ["multi-agent", "survey", "orchestration"]


@pytest.mark.asyncio
async def test_enrich_renders_prompt_with_title_and_content():
    response_json = json.dumps(
        {"summary": "요약", "category": "agent", "tags": ["test"]}
    )
    fake = FakeLLMClient(response=response_json)
    extractor = MetadataExtractor(
        llm_client=fake,
        prompt_template="T:{title}\nC:{content}",
    )

    await extractor.enrich(_doc(title="My Title", content="My Body"))

    assert len(fake.calls) == 1
    assert "T:My Title" in fake.calls[0]
    assert "C:My Body" in fake.calls[0]


@pytest.mark.asyncio
async def test_enrich_coerces_invalid_category_to_agent_default():
    response_json = json.dumps(
        {"summary": "요약", "category": "other", "tags": []}
    )
    extractor = MetadataExtractor(
        llm_client=FakeLLMClient(response=response_json),
        prompt_template="{title} {content}",
    )

    enriched = await extractor.enrich(_doc())

    assert enriched.category == "agent"


@pytest.mark.asyncio
async def test_enrich_normalizes_tags_to_lowercase_hyphenated():
    response_json = json.dumps(
        {
            "summary": "요약",
            "category": "rag",
            "tags": ["Multi Agent", " RAG ", "TOOL_USE"],
        }
    )
    extractor = MetadataExtractor(
        llm_client=FakeLLMClient(response=response_json),
        prompt_template="{title} {content}",
    )

    enriched = await extractor.enrich(_doc())

    assert enriched.tags == ["multi-agent", "rag", "tool-use"]


@pytest.mark.asyncio
async def test_enrich_raises_on_invalid_json():
    extractor = MetadataExtractor(
        llm_client=FakeLLMClient(response="not a json"),
        prompt_template="{title} {content}",
    )

    with pytest.raises(ValueError):
        await extractor.enrich(_doc())


@pytest.mark.asyncio
async def test_enrich_keeps_unrelated_fields_intact():
    response_json = json.dumps(
        {"summary": "새 요약", "category": "rag", "tags": ["a"]}
    )
    extractor = MetadataExtractor(
        llm_client=FakeLLMClient(response=response_json),
        prompt_template="{title} {content}",
    )

    enriched = await extractor.enrich(_doc(metadata={"author": "Alice", "score": 42}))

    assert enriched.metadata == {"author": "Alice", "score": 42}
    assert enriched.title == "Multi-Agent Orchestration Survey"
    assert enriched.url == "https://huggingface.co/papers/2405.01234"
