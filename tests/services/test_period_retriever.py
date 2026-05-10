from datetime import date

from app.services.period_retriever import (
    DateRange,
    PeriodRetrievalRequest,
    PeriodRetriever,
    PeriodSearchResult,
)


class FakePeriodSearchClient:
    def __init__(self, results_by_period: dict[tuple[date, date], list[PeriodSearchResult]]) -> None:
        self.results_by_period = results_by_period
        self.calls: list[dict] = []

    def search(
        self,
        *,
        query: str,
        top_k: int,
        date_from: date,
        date_to: date,
        sources: list[str],
    ) -> list[PeriodSearchResult]:
        # 기간/쿼리 조건으로 검색 호출이 들어오는지 기록
        self.calls.append(
            {
                "query": query,
                "top_k": top_k,
                "date_from": date_from,
                "date_to": date_to,
                "sources": sources,
            }
        )
        return self.results_by_period.get((date_from, date_to), [])


def _result(doc_id: str, content: str) -> PeriodSearchResult:
    # 테스트용 최소 검색 결과 생성
    return PeriodSearchResult(doc_id=doc_id, content=content)


def test_period_retriever_fetches_context_for_each_period():
    # 두 기간에 대해 각각 검색하고 결과를 구조화하는지 확인
    period_a = DateRange(start=date(2026, 4, 27), end=date(2026, 5, 3))
    period_b = DateRange(start=date(2026, 5, 4), end=date(2026, 5, 10))
    client = FakePeriodSearchClient(
        {
            (period_a.start, period_a.end): [_result("a1", "context a")],
            (period_b.start, period_b.end): [_result("b1", "context b")],
        }
    )
    retriever = PeriodRetriever(search_client=client)
    request = PeriodRetrievalRequest(
        period_a=period_a,
        period_b=period_b,
        focus_keywords=["LangGraph"],
        top_k=3,
    )

    result = retriever.retrieve(request)

    assert client.calls[0]["query"] == "AI Agent Trend Comparison LangGraph"
    assert client.calls[0]["top_k"] == 3
    assert client.calls[0]["date_from"] == period_a.start
    assert client.calls[0]["date_to"] == period_a.end
    assert client.calls[0]["sources"] == ["huggingface", "hackernews"]

    assert client.calls[1]["date_from"] == period_b.start
    assert client.calls[1]["date_to"] == period_b.end

    assert result.context_a.period == {"start": "2026-04-27", "end": "2026-05-03"}
    assert result.context_b.period == {"start": "2026-05-04", "end": "2026-05-10"}
    assert result.context_a.total_count == 1
    assert result.context_b.total_count == 1
    assert result.context_a.documents == [{"doc_id": "a1", "content": "context a"}]
    assert result.context_b.documents == [{"doc_id": "b1", "content": "context b"}]


def test_period_retriever_returns_empty_context_when_no_results():
    # 검색 결과가 없을 때 빈 컨텍스트를 반환하는지 확인
    period_a = DateRange(start=date(2026, 4, 27), end=date(2026, 5, 3))
    period_b = DateRange(start=date(2026, 5, 4), end=date(2026, 5, 10))
    client = FakePeriodSearchClient({})
    retriever = PeriodRetriever(search_client=client)

    result = retriever.retrieve(
        PeriodRetrievalRequest(
            period_a=period_a,
            period_b=period_b,
            focus_keywords=[],
            top_k=5,
        )
    )

    assert result.context_a.total_count == 0
    assert result.context_a.documents == []
    assert result.context_b.total_count == 0
    assert result.context_b.documents == []
