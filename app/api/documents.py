"""문서 검색 API 라우터."""

from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.agents.retriever import Retriever
from app.core.chroma_client import ChromaClient
from app.core.embedding_client import EmbeddingClient
from app.core.models import Source
from app.core.settings import Settings, get_settings

router = APIRouter()


class DocumentSearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=10, ge=1, le=50)
    date_from: date | None = None
    date_to: date | None = None
    sources: list[Source] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)


class SearchResultItem(BaseModel):
    document_id: str
    title: str
    source: str
    url: str
    published_at: date | None
    similarity_score: float
    summary_preview: str


class DocumentSearchData(BaseModel):
    rewritten_query: str
    results: list[SearchResultItem]


class DocumentSearchResponse(BaseModel):
    success: bool
    data: DocumentSearchData | None = None
    error: str | None = None


def get_retriever(settings: Settings = Depends(get_settings)) -> Retriever:
    embedding_client = EmbeddingClient(settings)
    chroma = ChromaClient(settings)
    return Retriever(embedding_client, chroma)


@router.post("/documents/search", response_model=DocumentSearchResponse)
def search_documents(
    request: DocumentSearchRequest,
    retriever: Retriever = Depends(get_retriever),
) -> DocumentSearchResponse:
    results = retriever.search(
        query=request.query,
        top_k=request.top_k,
        date_from=request.date_from,
        date_to=request.date_to,
        sources=request.sources or None,
        categories=request.categories or None,
    )

    items = [
        SearchResultItem(
            document_id=r.document_id,
            title=r.title,
            source=r.source,
            url=r.url,
            published_at=r.published_at,
            similarity_score=r.similarity_score,
            summary_preview=r.summary_preview,
        )
        for r in results
    ]

    return DocumentSearchResponse(
        success=True,
        data=DocumentSearchData(rewritten_query=request.query, results=items),
    )
