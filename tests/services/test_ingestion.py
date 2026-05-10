"""IngestionService 단위 테스트."""

from unittest.mock import MagicMock

import pytest

from app.agents.relevance_filter import RelevanceDecision
from app.core.models import Chunk, NormalizedDocument
from app.services.ingestion import IngestionResult, IngestionService


def make_document(doc_id: str = "doc_001") -> NormalizedDocument:
    return NormalizedDocument(
        doc_id=doc_id,
        source="huggingface",
        title="테스트 논문",
        url="https://huggingface.co/papers/test",
        published_date="2026-05-10",
        raw_text="LLM 기반 멀티에이전트 시스템에 관한 논문",
        category_hint="multi-agent",
        external_id="2405.00001",
        content_hash="sha256:abc",
    )


def make_decision(is_relevant: bool = True, doc_id: str = "doc_001") -> RelevanceDecision:
    return RelevanceDecision(
        document=make_document(doc_id),
        is_relevant=is_relevant,
        score=0.92,
        matched_keywords=["langgraph", "multi-agent"],
        reason="관련 문서",
    )


def make_service(chunks: list[Chunk] | None = None) -> tuple[IngestionService, MagicMock, MagicMock, MagicMock]:
    chunker = MagicMock()
    embedder = MagicMock()
    chroma = MagicMock()

    if chunks is None:
        chunks = [
            Chunk(
                chunk_id="doc_001_chunk_0",
                document_id="doc_001",
                chunk_index=0,
                text="청크 텍스트",
                metadata={"source": "huggingface"},
            )
        ]
    chunker.chunk.return_value = chunks

    embedded = MagicMock()
    embedded.chunk = chunks[0] if chunks else None
    embedded.vector = [0.1] * 4096
    embedder.embed_batch.return_value = [embedded] if chunks else []

    service = IngestionService(chunker=chunker, embedder=embedder, chroma=chroma)
    return service, chunker, embedder, chroma


def test_ingest_irrelevant_skips_storage():
    service, chunker, embedder, chroma = make_service()
    decision = make_decision(is_relevant=False)

    result = service.ingest(decision)

    assert result.skipped is True
    assert result.chunk_count == 0
    chunker.chunk.assert_not_called()
    chroma.add_batch.assert_not_called()


def test_ingest_relevant_calls_chunker():
    service, chunker, embedder, chroma = make_service()
    decision = make_decision()

    service.ingest(decision)

    chunker.chunk.assert_called_once()
    call_arg = chunker.chunk.call_args[0][0]
    assert call_arg.document.doc_id == "doc_001"
    assert call_arg.relevance_score == 0.92
    assert call_arg.matched_keywords == ["langgraph", "multi-agent"]


def test_ingest_stores_to_chroma():
    service, chunker, embedder, chroma = make_service()

    result = service.ingest(make_decision())

    chroma.add_batch.assert_called_once()
    assert result.chunk_count == 1
    assert result.skipped is False


def test_ingest_empty_chunks_skips_storage():
    service, chunker, embedder, chroma = make_service(chunks=[])
    embedder.embed_batch.return_value = []

    result = service.ingest(make_decision())

    assert result.chunk_count == 0
    chroma.add_batch.assert_not_called()


def test_ingest_batch_processes_all():
    service, chunker, embedder, chroma = make_service()
    decisions = [make_decision(doc_id=f"doc_{i:03d}") for i in range(3)]
    chunker.chunk.return_value = [
        Chunk(
            chunk_id="doc_chunk_0",
            document_id="doc",
            chunk_index=0,
            text="텍스트",
            metadata={},
        )
    ]

    results = service.ingest_batch(decisions)

    assert len(results) == 3
    assert chunker.chunk.call_count == 3
