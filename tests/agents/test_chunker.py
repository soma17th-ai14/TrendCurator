"""Chunker 단위 테스트."""

import pytest

from app.agents.chunker import Chunker
from app.core.models import Chunk, ChunkingInput, NormalizedDocument


def make_input(raw_text: str = "테스트 텍스트") -> ChunkingInput:
    return ChunkingInput(
        document=NormalizedDocument(
            doc_id="doc_001",
            source="huggingface",
            title="테스트 논문",
            url="https://huggingface.co/papers/test",
            published_date="2026-05-06",
            raw_text=raw_text,
            category_hint="multi-agent",
            external_id="2405.01234",
            content_hash="sha256:abc",
        ),
        relevance_score=0.93,
        matched_keywords=["langgraph", "multi-agent"],
    )


def test_chunk_returns_list_of_chunks():
    chunker = Chunker()
    result = chunker.chunk(make_input("짧은 텍스트"))

    assert len(result) >= 1
    assert all(isinstance(c, Chunk) for c in result)


def test_chunk_id_format():
    chunker = Chunker()
    result = chunker.chunk(make_input("텍스트"))

    assert result[0].chunk_id == "doc_001_chunk_0"
    assert result[0].document_id == "doc_001"
    assert result[0].chunk_index == 0


def test_chunk_metadata_contains_required_fields():
    chunker = Chunker()
    result = chunker.chunk(make_input("텍스트"))
    metadata = result[0].metadata

    assert metadata["document_id"] == "doc_001"
    assert metadata["source"] == "huggingface"
    assert metadata["published_at"] == "2026-05-06"
    assert metadata["relevance_score"] == 0.93
    assert metadata["matched_keywords"] == ["langgraph", "multi-agent"]


def test_long_text_splits_into_multiple_chunks():
    chunker = Chunker(chunk_size=100, overlap=10)
    long_text = "단어 " * 100  # ~400자

    result = chunker.chunk(make_input(long_text))

    assert len(result) > 1


def test_chunks_cover_full_text():
    chunker = Chunker(chunk_size=50, overlap=0)
    text = "a" * 120

    result = chunker.chunk(make_input(text))
    combined = "".join(c.text for c in result)

    assert len(combined) >= len(text.strip())


def test_empty_text_returns_empty_list():
    chunker = Chunker()
    result = chunker.chunk(make_input(""))

    assert result == []


def test_chunk_batch_processes_multiple_inputs():
    chunker = Chunker()
    inputs = [make_input("텍스트1"), make_input("텍스트2")]

    result = chunker.chunk_batch(inputs)

    assert len(result) >= 2
    assert result[0].chunk_id.startswith("doc_001_chunk_")
