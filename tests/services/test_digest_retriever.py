from datetime import date

from app.core.models import DailyDigestRetrievalRequest
from app.services.digest_retriever import DailyDigestRetriever, DigestSearchResult


class FakeDocumentSearchClient:
    def __init__(self, results: list[DigestSearchResult]) -> None:
        self.results = results
        self.calls: list[dict] = []

    def search(
        self,
        *,
        query: str,
        top_k: int,
        date_from: date,
        date_to: date,
        sources: list[str],
    ) -> list[DigestSearchResult]:
        self.calls.append(
            {
                "query": query,
                "top_k": top_k,
                "date_from": date_from,
                "date_to": date_to,
                "sources": sources,
            }
        )
        return self.results


def _search_result(**overrides) -> DigestSearchResult:
    base = {
        "document_id": "doc_001",
        "source": "huggingface",
        "title": "LangGraph Agent Workflow",
        "url": "https://example.com/doc_001",
        "published_at": date(2026, 5, 5),
        "content": "LangGraph multi-agent workflow content",
        "summary_preview": "LangGraph workflow summary",
        "similarity_score": 0.8,
        "relevance_score": 0.9,
        "matched_keywords": ["langgraph", "multi-agent"],
        "tags": ["agent", "workflow"],
        "metadata": {"external_id": "2405.00001"},
    }
    base.update(overrides)
    return DigestSearchResult(**base)


def test_retriever_builds_search_request_from_digest_request():
    client = FakeDocumentSearchClient([_search_result()])
    retriever = DailyDigestRetriever(search_client=client)
    request = DailyDigestRetrievalRequest(
        digest_date=date(2026, 5, 6),
        lookback_days=2,
        top_k=5,
        keywords=["LangGraph", "RAG"],
        sources=["huggingface"],
    )

    result = retriever.retrieve(request)

    assert client.calls == [
        {
            "query": "AI Agent Daily Digest LangGraph RAG",
            "top_k": 15,
            "date_from": date(2026, 5, 4),
            "date_to": date(2026, 5, 6),
            "sources": ["huggingface"],
        }
    ]
    assert result.digest_date == date(2026, 5, 6)
    assert result.selected_count == 1
    assert result.candidates[0].document_id == "doc_001"


def test_retriever_filters_deduplicates_ranks_and_limits_candidates():
    client = FakeDocumentSearchClient(
        [
            _search_result(document_id="doc_low", relevance_score=0.17),
            _search_result(
                document_id="doc_duplicate",
                title="Lower duplicate",
                similarity_score=0.7,
                relevance_score=0.7,
            ),
            _search_result(
                document_id="doc_duplicate",
                title="Higher duplicate",
                similarity_score=0.9,
                relevance_score=0.8,
            ),
            _search_result(
                document_id="doc_top",
                title="Top candidate",
                similarity_score=0.6,
                relevance_score=0.95,
            ),
            _search_result(
                document_id="doc_second",
                title="Second candidate",
                similarity_score=0.95,
                relevance_score=0.75,
            ),
        ]
    )
    retriever = DailyDigestRetriever(search_client=client)
    request = DailyDigestRetrievalRequest(
        digest_date=date(2026, 5, 6),
        top_k=2,
        min_relevance_score=0.18,
    )

    result = retriever.retrieve(request)

    assert result.total_count == 3
    assert result.selected_count == 2
    assert [candidate.document_id for candidate in result.candidates] == [
        "doc_top",
        "doc_duplicate",
    ]
    assert result.candidates[1].title == "Higher duplicate"


def test_retriever_uses_content_preview_when_summary_is_empty():
    client = FakeDocumentSearchClient(
        [
            _search_result(
                summary_preview="",
                content="  " + ("agent memory " * 30),
            )
        ]
    )
    retriever = DailyDigestRetriever(search_client=client)

    result = retriever.retrieve(DailyDigestRetrievalRequest(digest_date=date(2026, 5, 6)))

    assert result.candidates[0].summary_preview.startswith("agent memory")
    assert len(result.candidates[0].summary_preview) == 240


def test_retriever_uses_base_query_when_profile_keywords_are_disabled():
    client = FakeDocumentSearchClient([])
    retriever = DailyDigestRetriever(search_client=client)
    request = DailyDigestRetrievalRequest(
        digest_date=date(2026, 5, 6),
        profile_based=False,
        keywords=["LangGraph"],
    )

    result = retriever.retrieve(request)

    assert client.calls[0]["query"] == "AI Agent Daily Digest"
    assert result.total_count == 0
    assert result.selected_count == 0
