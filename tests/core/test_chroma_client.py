"""ChromaClient 단위 테스트.

EphemeralClient 기반으로 실제 ChromaDB 로직을 검증한다.
파일 I/O 없이 메모리에서만 실행되므로 CI 환경에서도 안전하다.
"""

import uuid

import pytest

from app.core.chroma_client import ChromaClient, SearchResult

FAKE_VECTOR = [0.1] * 4096
ANOTHER_VECTOR = [0.9] * 4096


@pytest.fixture
def client() -> ChromaClient:
    return ChromaClient.ephemeral(collection_name=str(uuid.uuid4()))


def test_add_and_count(client):
    client.add(
        chunk_id="chunk_001",
        text="LangGraph multi-agent workflow",
        vector=FAKE_VECTOR,
        metadata={"document_id": "doc_001", "source": "huggingface"},
    )
    assert client.count() == 1


def test_add_batch_and_count(client):
    client.add_batch(
        chunk_ids=["chunk_001", "chunk_002", "chunk_003"],
        texts=["텍스트1", "텍스트2", "텍스트3"],
        vectors=[FAKE_VECTOR, FAKE_VECTOR, FAKE_VECTOR],
        metadatas=[
            {"document_id": "doc_001", "source": "huggingface"},
            {"document_id": "doc_001", "source": "huggingface"},
            {"document_id": "doc_002", "source": "hackernews"},
        ],
    )
    assert client.count() == 3


def test_search_returns_results(client):
    client.add(
        chunk_id="chunk_001",
        text="LangGraph multi-agent workflow",
        vector=FAKE_VECTOR,
        metadata={"document_id": "doc_001", "source": "huggingface"},
    )

    results = client.search(query_vector=FAKE_VECTOR, top_k=1)

    assert len(results) == 1
    assert isinstance(results[0], SearchResult)
    assert results[0].chunk_id == "chunk_001"
    assert results[0].document_id == "doc_001"
    assert 0.0 <= results[0].similarity_score <= 1.0


def test_search_similarity_score_range(client):
    client.add(
        chunk_id="chunk_001",
        text="동일한 벡터 문서",
        vector=FAKE_VECTOR,
        metadata={"document_id": "doc_001", "source": "huggingface"},
    )
    client.add(
        chunk_id="chunk_002",
        text="다른 벡터 문서",
        vector=ANOTHER_VECTOR,
        metadata={"document_id": "doc_002", "source": "hackernews"},
    )

    results = client.search(query_vector=FAKE_VECTOR, top_k=2)

    assert results[0].similarity_score >= results[1].similarity_score


def test_search_with_where_filter(client):
    client.add_batch(
        chunk_ids=["chunk_001", "chunk_002"],
        texts=["huggingface 문서", "hackernews 문서"],
        vectors=[FAKE_VECTOR, FAKE_VECTOR],
        metadatas=[
            {"document_id": "doc_001", "source": "huggingface"},
            {"document_id": "doc_002", "source": "hackernews"},
        ],
    )

    results = client.search(
        query_vector=FAKE_VECTOR,
        top_k=10,
        where={"source": {"$eq": "huggingface"}},
    )

    assert len(results) == 1
    assert results[0].metadata["source"] == "huggingface"


def test_delete_removes_chunks(client):
    client.add(
        chunk_id="chunk_001",
        text="삭제될 문서",
        vector=FAKE_VECTOR,
        metadata={"document_id": "doc_001", "source": "huggingface"},
    )
    assert client.count() == 1

    client.delete(["chunk_001"])

    assert client.count() == 0


def test_get_texts_by_document_ids(client):
    client.add_batch(
        chunk_ids=["chunk_001", "chunk_002", "chunk_003"],
        texts=["first context", "second context", "other context"],
        vectors=[FAKE_VECTOR, FAKE_VECTOR, FAKE_VECTOR],
        metadatas=[
            {"document_id": "doc_001", "source": "huggingface"},
            {"document_id": "doc_001", "source": "huggingface"},
            {"document_id": "doc_002", "source": "hackernews"},
        ],
    )

    texts = client.get_texts_by_document_ids(["doc_001"])

    assert texts == ["first context", "second context"]
