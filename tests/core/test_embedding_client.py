"""EmbeddingClient 단위 테스트."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.embedding_client import EmbeddingClient
from app.core.settings import Settings


FAKE_VECTOR = [0.1] * 4096


def make_settings() -> Settings:
    return Settings(
        solar_api_key="test-key",
        solar_base_url="https://api.upstage.ai/v1",
        solar_embedding_passage_model="embedding-passage",
        solar_embedding_query_model="embedding-query",
    )


def make_mock_response(vector: list[float]) -> MagicMock:
    mock = MagicMock()
    mock.json.return_value = {"data": [{"embedding": vector}]}
    mock.raise_for_status = MagicMock()
    return mock


@patch("app.core.embedding_client.httpx.post")
def test_embed_passage_returns_vector(mock_post):
    mock_post.return_value = make_mock_response(FAKE_VECTOR)
    client = EmbeddingClient(make_settings())

    result = client.embed_passage("테스트 문서")

    assert result == FAKE_VECTOR
    mock_post.assert_called_once()
    call_kwargs = mock_post.call_args
    assert call_kwargs.kwargs["json"]["model"] == "embedding-passage"


@patch("app.core.embedding_client.httpx.post")
def test_embed_query_uses_query_model(mock_post):
    mock_post.return_value = make_mock_response(FAKE_VECTOR)
    client = EmbeddingClient(make_settings())

    result = client.embed_query("검색 쿼리")

    assert result == FAKE_VECTOR
    call_kwargs = mock_post.call_args
    assert call_kwargs.kwargs["json"]["model"] == "embedding-query"


@patch("app.core.embedding_client.httpx.post")
def test_embed_passages_returns_multiple_vectors(mock_post):
    mock_post.return_value = make_mock_response(FAKE_VECTOR)
    client = EmbeddingClient(make_settings())

    results = client.embed_passages(["문서1", "문서2", "문서3"])

    assert len(results) == 3
    assert all(v == FAKE_VECTOR for v in results)
    assert mock_post.call_count == 3


@patch("app.core.embedding_client.httpx.post")
def test_embed_raises_on_http_error(mock_post):
    import httpx
    mock_post.return_value = MagicMock(
        raise_for_status=MagicMock(side_effect=httpx.HTTPStatusError(
            "400", request=MagicMock(), response=MagicMock()
        ))
    )
    client = EmbeddingClient(make_settings())

    with pytest.raises(httpx.HTTPStatusError):
        client.embed_passage("테스트")
