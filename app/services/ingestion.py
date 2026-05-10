"""VectorDB 저장 파이프라인.

RelevanceDecision → ChunkingInput 어댑터를 포함하며,
청킹 → 임베딩 → ChromaDB 저장 전 과정을 orchestration한다.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.agents.chunker import Chunker
from app.agents.embedder import Embedder
from app.agents.relevance_filter import RelevanceDecision
from app.core.chroma_client import ChromaClient
from app.core.models import ChunkingInput


@dataclass
class IngestionResult:
    document_id: str
    chunk_count: int
    skipped: bool = False


class IngestionService:
    """관련성 필터 결과를 VectorDB에 저장한다."""

    def __init__(
        self,
        chunker: Chunker,
        embedder: Embedder,
        chroma: ChromaClient,
    ) -> None:
        self._chunker = chunker
        self._embedder = embedder
        self._chroma = chroma

    def ingest(self, decision: RelevanceDecision) -> IngestionResult:
        if not decision.is_relevant:
            return IngestionResult(
                document_id=decision.document.doc_id,
                chunk_count=0,
                skipped=True,
            )

        chunking_input = _to_chunking_input(decision)
        chunks = self._chunker.chunk(chunking_input)

        if not chunks:
            return IngestionResult(document_id=decision.document.doc_id, chunk_count=0)

        embedded = self._embedder.embed_batch(chunks)

        self._chroma.add_batch(
            chunk_ids=[e.chunk.chunk_id for e in embedded],
            texts=[e.chunk.text for e in embedded],
            vectors=[e.vector for e in embedded],
            metadatas=[_sanitize_metadata(e.chunk.metadata) for e in embedded],
        )

        return IngestionResult(
            document_id=decision.document.doc_id,
            chunk_count=len(embedded),
        )

    def ingest_batch(self, decisions: list[RelevanceDecision]) -> list[IngestionResult]:
        return [self.ingest(d) for d in decisions]


def _sanitize_metadata(metadata: dict) -> dict:
    """ChromaDB는 list 타입 메타데이터를 지원하지 않아 쉼표 구분 문자열로 직렬화한다."""
    return {k: ",".join(v) if isinstance(v, list) else v for k, v in metadata.items()}


def _to_chunking_input(decision: RelevanceDecision) -> ChunkingInput:
    return ChunkingInput(
        document=decision.document,
        relevance_score=decision.score,
        matched_keywords=decision.matched_keywords,
    )
