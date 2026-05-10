"""청크 임베딩 모듈."""

from __future__ import annotations

from dataclasses import dataclass

from app.core.embedding_client import EmbeddingClient
from app.core.models import Chunk


@dataclass
class EmbeddedChunk:
    """임베딩 벡터가 첨부된 청크."""

    chunk: Chunk
    vector: list[float]


class Embedder:
    """Chunk 리스트를 받아 Solar embedding-passage 벡터를 생성한다."""

    def __init__(self, client: EmbeddingClient) -> None:
        self._client = client

    def embed(self, chunk: Chunk) -> EmbeddedChunk:
        vector = self._client.embed_passage(chunk.text)
        return EmbeddedChunk(chunk=chunk, vector=vector)

    def embed_batch(self, chunks: list[Chunk]) -> list[EmbeddedChunk]:
        if not chunks:
            return []
        texts = [c.text for c in chunks]
        vectors = self._client.embed_passages(texts)
        return [EmbeddedChunk(chunk=c, vector=v) for c, v in zip(chunks, vectors)]
