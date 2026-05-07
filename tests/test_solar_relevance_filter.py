from app.agents.solar_relevance_filter import SolarMiniLLMRelevanceFilter
from app.core.models import NormalizedDocument
from app.core.settings import SolarSettings


class FakeSolarJsonClient:
    """실제 Solar API를 호출하지 않고 연결부만 검증하기 위한 가짜 클라이언트입니다."""

    def __init__(self, response):
        self.response = response
        self.calls = []

    def chat_json(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def make_document():
    return NormalizedDocument(
        doc_id="doc_001",
        title="LangGraph agent workflow",
        source="huggingface",
        url="https://example.com/doc",
        published_date="2026-05-08",
        raw_text="A paper about multi-agent orchestration.",
        category_hint="langgraph workflow",
        external_id="doc_001",
        content_hash="hash_doc_001",
        metadata={"authors": ["Author A"]},
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


def test_solar_mini_llm_relevance_filter_parses_string_false():
    client = FakeSolarJsonClient(
        {
            "is_relevant": "false",
            "score": 0.04,
            "matched_keywords": [],
            "reason": "AI Agent 관련 신호가 기준보다 약합니다.",
        }
    )
    settings = SolarSettings(api_key="test-key", mini_model="solar-mini-test")
    filter_ = SolarMiniLLMRelevanceFilter(client=client, settings=settings)

    decision = filter_.evaluate(make_document())

    assert decision.is_relevant is False


def test_solar_mini_llm_relevance_filter_rejects_low_score_even_if_flag_is_true():
    client = FakeSolarJsonClient(
        {
            "is_relevant": True,
            "score": 0.04,
            "matched_keywords": [],
            "reason": "AI Agent 관련 신호가 기준보다 약합니다.",
        }
    )
    settings = SolarSettings(api_key="test-key", mini_model="solar-mini-test")
    filter_ = SolarMiniLLMRelevanceFilter(client=client, settings=settings)

    decision = filter_.evaluate(make_document())

    assert decision.is_relevant is False
