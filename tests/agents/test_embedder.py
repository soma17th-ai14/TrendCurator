"""Embedder 단위 테스트."""

from unittest.mock import MagicMock

import pytest

from app.agents.embedder import EmbeddedChunk, Embedder
from app.core.models import Chunk


def make_chunk(index: int = 0) -> Chunk:
    return Chunk(
        chunk_id=f"doc_001_chunk_{index}",
        document_id="doc_001",
        chunk_index=index,
        text=f"청크 텍스트 {index}",
        metadata={"source": "huggingface"},
    )


def make_client(dim: int = 4096) -> MagicMock:
    client = MagicMock()
    client.embed_passage.return_value = [0.1] * dim
    client.embed_passages.side_effect = lambda texts: [[0.1] * dim for _ in texts]
    return client


def test_embed_returns_embedded_chunk():
    embedder = Embedder(make_client())
    result = embedder.embed(make_chunk())

    assert isinstance(result, EmbeddedChunk)
    assert result.chunk.chunk_id == "doc_001_chunk_0"
    assert len(result.vector) == 4096


def test_embed_calls_embed_passage():
    client = make_client()
    embedder = Embedder(client)
    chunk = make_chunk()

    embedder.embed(chunk)

    client.embed_passage.assert_called_once_with(chunk.text)


def test_embed_batch_returns_same_count():
    embedder = Embedder(make_client())
    chunks = [make_chunk(i) for i in range(3)]

    result = embedder.embed_batch(chunks)

    assert len(result) == 3
    assert all(isinstance(r, EmbeddedChunk) for r in result)


def test_embed_batch_empty_returns_empty():
    embedder = Embedder(make_client())

    result = embedder.embed_batch([])

    assert result == []


def test_embed_batch_calls_embed_passages():
    client = make_client()
    embedder = Embedder(client)
    chunks = [make_chunk(i) for i in range(2)]

    embedder.embed_batch(chunks)

    client.embed_passages.assert_called_once_with([c.text for c in chunks])


def test_embed_batch_preserves_chunk_order():
    embedder = Embedder(make_client())
    chunks = [make_chunk(i) for i in range(3)]

    result = embedder.embed_batch(chunks)

    for i, embedded in enumerate(result):
        assert embedded.chunk.chunk_index == i
