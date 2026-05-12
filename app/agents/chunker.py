"""텍스트 청킹 모듈."""

from __future__ import annotations

from app.core.models import Chunk, ChunkingInput

CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


class Chunker:
    """ChunkingInput을 받아 Chunk 리스트로 분할한다."""

    def __init__(self, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> None:
        self._chunk_size = chunk_size
        self._overlap = overlap

    def chunk(self, input: ChunkingInput) -> list[Chunk]:
        doc = input.document
        texts = self._split(doc.raw_text)
        metadata = self._base_metadata(input)

        return [
            Chunk(
                chunk_id=f"{doc.doc_id}_chunk_{i}",
                document_id=doc.doc_id,
                chunk_index=i,
                text=text,
                metadata=metadata,
            )
            for i, text in enumerate(texts)
        ]

    def chunk_batch(self, inputs: list[ChunkingInput]) -> list[Chunk]:
        chunks = []
        for input in inputs:
            chunks.extend(self.chunk(input))
        return chunks

    def _split(self, text: str) -> list[str]:
        if not text:
            return []

        chunks = []
        start = 0
        while start < len(text):
            end = min(start + self._chunk_size, len(text))
            # 청크 경계가 단어 중간이면 마지막 공백 기준으로 자름
            if end < len(text) and text[end] not in (" ", "\n"):
                boundary = text.rfind(" ", start, end)
                if boundary > start:
                    end = boundary
            chunks.append(text[start:end].strip())
            start = end - self._overlap if end < len(text) else end

        return [c for c in chunks if c]

    def _base_metadata(self, input: ChunkingInput) -> dict:
        doc = input.document
        published_at_int = int(doc.published_date.replace("-", "")) if doc.published_date else 0
        return {
            "document_id": doc.doc_id,
            "source": doc.source,
            "title": doc.title,
            "url": doc.url,
            "published_at": doc.published_date,
            "published_at_int": published_at_int,
            "category": doc.category_hint,
            "relevance_score": input.relevance_score,
            "matched_keywords": input.matched_keywords,
        }
