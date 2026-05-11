"""ChromaDB 클라이언트."""

from __future__ import annotations

from dataclasses import dataclass

import chromadb

from app.core.settings import Settings


@dataclass
class SearchResult:
    chunk_id: str
    document_id: str
    text: str
    similarity_score: float
    metadata: dict


class ChromaClient:
    """ChromaDB 저장 및 검색 클라이언트."""

    def __init__(
        self,
        settings: Settings,
        client: chromadb.Client | None = None,
    ) -> None:
        self._client = client or chromadb.PersistentClient(path=settings.chroma_data_path)
        self._collection = self._client.get_or_create_collection(
            name=settings.chroma_collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @classmethod
    def ephemeral(cls, collection_name: str = "test") -> "ChromaClient":
        """테스트용 메모리 기반 클라이언트."""
        settings = Settings(
            solar_api_key="test",
            chroma_collection_name=collection_name,
        )
        return cls(settings, client=chromadb.EphemeralClient())

    def add(
        self,
        chunk_id: str,
        text: str,
        vector: list[float],
        metadata: dict,
    ) -> None:
        """청크 하나를 저장한다."""
        self._collection.add(
            ids=[chunk_id],
            documents=[text],
            embeddings=[vector],
            metadatas=[metadata],
        )

    def add_batch(
        self,
        chunk_ids: list[str],
        texts: list[str],
        vectors: list[list[float]],
        metadatas: list[dict],
    ) -> None:
        """청크 배치를 저장한다."""
        self._collection.add(
            ids=chunk_ids,
            documents=texts,
            embeddings=vectors,
            metadatas=metadatas,
        )

    def search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        where: dict | None = None,
    ) -> list[SearchResult]:
        """쿼리 벡터와 유사한 청크를 검색한다."""
        kwargs: dict = {"query_embeddings": [query_vector], "n_results": top_k}
        if where:
            kwargs["where"] = where

        results = self._collection.query(**kwargs)

        search_results = []
        ids = results["ids"][0]
        documents = results["documents"][0]
        distances = results["distances"][0]
        metadatas = results["metadatas"][0]

        for chunk_id, text, distance, metadata in zip(ids, documents, distances, metadatas):
            search_results.append(SearchResult(
                chunk_id=chunk_id,
                document_id=metadata.get("document_id", ""),
                text=text,
                similarity_score=round(max(0.0, min(1.0, 1 - distance)), 4),
                metadata=metadata,
            ))

        return search_results

    def count(self) -> int:
        return self._collection.count()

    def get_texts_by_document_ids(self, document_ids: list[str]) -> list[str]:
        if not document_ids:
            return []

        results = self._collection.get(
            where={"document_id": {"$in": document_ids}},
            include=["documents"],
        )
        documents = results.get("documents") or []
        return [text for text in documents if isinstance(text, str)]

    def delete(self, chunk_ids: list[str]) -> None:
        self._collection.delete(ids=chunk_ids)
