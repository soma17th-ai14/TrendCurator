"""ChromaDB 클라이언트."""

from __future__ import annotations

from dataclasses import dataclass
import logging

import chromadb

from app.core.settings import Settings

logger = logging.getLogger(__name__)


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
        self._collection_name = settings.chroma_collection_name
        self._collection = self._get_or_create_collection()

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
        """청크 하나를 저장한다.

        동일 ``chunk_id`` 가 이미 있으면 덮어쓴다(upsert). ``chunk_id`` 는
        ``f"{doc_id}_chunk_{i}"`` 로 결정적으로 생성되므로, 동일 문서가 재수집되어도
        중복 row 가 쌓이지 않는다.
        """
        self._collection.upsert(
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
        """청크 배치를 저장한다. ``add`` 와 동일하게 ``chunk_id`` 기준 upsert 처리."""
        self._collection.upsert(
            ids=chunk_ids,
            documents=texts,
            embeddings=vectors,
            metadatas=metadatas,
        )

    def reset_collection(self) -> None:
        """저장된 모든 청크를 비운다.

        데모/시연 환경에서 부팅 시 깨끗한 상태로 시작하기 위해 사용한다. 컬렉션 자체를
        삭제 후 동일 이름으로 다시 만들고, 인스턴스 내부 참조도 새 컬렉션으로 교체한다.
        """
        name = self._collection.name
        try:
            self._client.delete_collection(name)
        except Exception:  # pragma: no cover - 컬렉션이 없을 때도 정상 흐름
            pass
        self._collection = self._get_or_create_collection(name)

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

        results = self._query_with_recovery(kwargs)

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

    def count_by_source(self) -> dict[str, int]:
        """source별 고유 document 수를 반환한다."""
        results = self._collection.get(include=["metadatas"])
        metadatas = results.get("metadatas") or []
        seen: dict[str, set[str]] = {}
        for meta in metadatas:
            source = meta.get("source", "")
            doc_id = meta.get("document_id", "")
            if source and doc_id:
                seen.setdefault(source, set()).add(doc_id)
        return {source: len(doc_ids) for source, doc_ids in seen.items()}

    def top_keywords(self, top_k: int = 10) -> list[dict]:
        """matched_keywords 빈도 기준 상위 키워드 목록을 반환한다."""
        results = self._collection.get(include=["metadatas"])
        metadatas = results.get("metadatas") or []
        seen_docs: set[str] = set()
        counts: dict[str, int] = {}
        for meta in metadatas:
            doc_id = meta.get("document_id", "")
            if not doc_id or doc_id in seen_docs:
                continue
            seen_docs.add(doc_id)
            keywords_raw = meta.get("matched_keywords", "")
            for kw in (k.strip() for k in keywords_raw.split(",") if k.strip()):
                counts[kw] = counts.get(kw, 0) + 1
        sorted_kws = sorted(counts.items(), key=lambda x: x[1], reverse=True)
        return [{"tag": kw, "count": cnt} for kw, cnt in sorted_kws[:top_k]]

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

    def _get_or_create_collection(self, name: str | None = None):
        return self._client.get_or_create_collection(
            name=name or self._collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    def _query_with_recovery(self, kwargs: dict):
        try:
            return self._collection.query(**kwargs)
        except Exception as exc:
            if not _is_stale_hnsw_error(exc):
                raise
            logger.warning("Chroma HNSW reader error; refreshing collection handle and retrying: %s", exc)
            self._collection = self._get_or_create_collection()
            return self._collection.query(**kwargs)


def _is_stale_hnsw_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "hnsw segment reader" in message or "nothing found on disk" in message
