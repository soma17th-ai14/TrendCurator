from app.agents.solar_relevance_filter import SolarMiniLLMRelevanceFilter
from app.core.models import Document
from app.core.settings import SolarSettings


class FakeSolarJsonClient:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def chat_json(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def make_document():
    return Document(
        document_id="doc_001",
        title="LangGraph agent workflow",
        source="huggingface",
        url="https://example.com/doc",
        published_at="2026-05-08",
        collected_at="2026-05-08T09:00:00",
        category="agent",
        tags=["langgraph", "workflow"],
        content="A paper about multi-agent orchestration.",
        summary="Agent workflow summary.",
        metadata={},
    )


def test_solar_mini_llm_relevance_filter_uses_configured_model():
    client = FakeSolarJsonClient(
        {
            "is_relevant": True,
            "score": 0.93,
            "matched_keywords": ["langgraph"],
            "reason": "LangGraph agent workflow를 다룹니다.",
        }
    )
    settings = SolarSettings(api_key="test-key", mini_model="solar-mini-test")
    filter_ = SolarMiniLLMRelevanceFilter(client=client, settings=settings)

    decision = filter_.evaluate(make_document())

    assert decision.is_relevant is True
    assert decision.score == 0.93
    assert client.calls[0]["model"] == "solar-mini-test"
