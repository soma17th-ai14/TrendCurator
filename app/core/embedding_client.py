"""Solar Embedding API 클라이언트."""

from __future__ import annotations

import httpx

from app.core.settings import Settings


class EmbeddingClient:
    """Solar embedding-passage / embedding-query 호출 클라이언트."""

    def __init__(self, settings: Settings, timeout: float = 30.0) -> None:
        self._api_key = settings.solar_api_key
        self._base_url = settings.solar_base_url
        self._passage_model = settings.solar_embedding_passage_model
        self._query_model = settings.solar_embedding_query_model
        self._timeout = timeout

    def embed_passage(self, text: str) -> list[float]:
        """문서 저장용 임베딩 (embedding-passage)."""
        return self._embed(text, self._passage_model)

    def embed_query(self, text: str) -> list[float]:
        """검색 쿼리용 임베딩 (embedding-query)."""
        return self._embed(text, self._query_model)

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        """복수 문서 배치 임베딩."""
        return [self.embed_passage(t) for t in texts]

    def _embed(self, text: str, model: str) -> list[float]:
        response = httpx.post(
            f"{self._base_url}/embeddings",
            headers={"Authorization": f"Bearer {self._api_key}"},
            json={"model": model, "input": text},
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response.json()["data"][0]["embedding"]
