import pytest

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


class FailingSolarJsonClient:
    def chat_json(self, **kwargs):
        raise RuntimeError("Solar API 요청 실패")


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
    assert "판정 기준" in client.calls[0]["messages"][0].content


def test_solar_mini_llm_relevance_filter_reuses_system_prompt(monkeypatch):
    load_count = 0

    def fake_load_system_prompt(self):
        nonlocal load_count
        load_count += 1
        return "cached system prompt"

    monkeypatch.setattr(
        SolarMiniLLMRelevanceFilter,
        "_load_system_prompt",
        fake_load_system_prompt,
    )
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

    filter_.evaluate(make_document())
    filter_.evaluate(make_document())

    assert load_count == 1
    assert client.calls[0]["messages"][0].content == "cached system prompt"
    assert client.calls[1]["messages"][0].content == "cached system prompt"


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


def test_solar_mini_llm_relevance_filter_uses_fallback_score_for_invalid_score():
    client = FakeSolarJsonClient(
        {
            "is_relevant": True,
            "score": "not-a-number",
            "matched_keywords": "langgraph",
            "reason": "점수 형식이 잘못된 응답입니다.",
        }
    )
    settings = SolarSettings(api_key="test-key", mini_model="solar-mini-test")
    filter_ = SolarMiniLLMRelevanceFilter(client=client, settings=settings)

    decision = filter_.evaluate(make_document())
    fallback = filter_.fallback_filter.evaluate(make_document())

    assert decision.is_relevant is fallback.is_relevant
    assert decision.score == fallback.score
    assert decision.matched_keywords == fallback.matched_keywords


def test_solar_mini_llm_relevance_filter_clamps_score_range():
    client = FakeSolarJsonClient(
        {
            "is_relevant": True,
            "score": 1.7,
            "matched_keywords": ["agent"],
            "reason": "점수 범위를 벗어난 응답입니다.",
        }
    )
    settings = SolarSettings(api_key="test-key", mini_model="solar-mini-test")
    filter_ = SolarMiniLLMRelevanceFilter(client=client, settings=settings)

    decision = filter_.evaluate(make_document())

    assert decision.is_relevant is True
    assert decision.score == 1.0


def test_solar_mini_llm_relevance_filter_uses_fallback_when_client_fails():
    settings = SolarSettings(api_key="test-key", mini_model="solar-mini-test")
    filter_ = SolarMiniLLMRelevanceFilter(client=FailingSolarJsonClient(), settings=settings)

    document = make_document()
    decision = filter_.evaluate(document)
    fallback = filter_.fallback_filter.evaluate(document)

    assert decision == fallback


def test_solar_mini_llm_relevance_filter_can_disable_error_fallback():
    settings = SolarSettings(api_key="test-key", mini_model="solar-mini-test")
    filter_ = SolarMiniLLMRelevanceFilter(
        client=FailingSolarJsonClient(),
        settings=settings,
        fallback_on_error=False,
    )

    with pytest.raises(RuntimeError, match="Solar 관련성 필터 호출이 실패했습니다."):
        filter_.evaluate(make_document())


def test_solar_mini_llm_relevance_filter_can_disable_invalid_response_fallback():
    settings = SolarSettings(api_key="test-key", mini_model="solar-mini-test")
    filter_ = SolarMiniLLMRelevanceFilter(
        client=FakeSolarJsonClient(["not", "a", "dict"]),
        settings=settings,
        fallback_on_error=False,
    )

    with pytest.raises(RuntimeError, match="JSON 객체가 아닙니다."):
        filter_.evaluate(make_document())


def test_solar_mini_llm_relevance_filter_strict_mode_rejects_invalid_score():
    settings = SolarSettings(api_key="test-key", mini_model="solar-mini-test")
    filter_ = SolarMiniLLMRelevanceFilter(
        client=FakeSolarJsonClient(
            {
                "is_relevant": True,
                "score": 1.7,
                "matched_keywords": ["agent"],
                "reason": "점수 범위를 벗어난 응답입니다.",
            }
        ),
        settings=settings,
        fallback_on_error=False,
    )

    with pytest.raises(RuntimeError, match="score 값이 유효하지 않습니다."):
        filter_.evaluate(make_document())


def test_solar_mini_llm_relevance_filter_strict_mode_rejects_bool_score():
    settings = SolarSettings(api_key="test-key", mini_model="solar-mini-test")
    filter_ = SolarMiniLLMRelevanceFilter(
        client=FakeSolarJsonClient(
            {
                "is_relevant": True,
                "score": True,
                "matched_keywords": ["agent"],
                "reason": "점수 타입이 잘못된 응답입니다.",
            }
        ),
        settings=settings,
        fallback_on_error=False,
    )

    with pytest.raises(RuntimeError, match="score 값이 유효하지 않습니다."):
        filter_.evaluate(make_document())


def test_solar_mini_llm_relevance_filter_strict_mode_rejects_invalid_keywords():
    settings = SolarSettings(api_key="test-key", mini_model="solar-mini-test")
    filter_ = SolarMiniLLMRelevanceFilter(
        client=FakeSolarJsonClient(
            {
                "is_relevant": True,
                "score": 0.7,
                "matched_keywords": ["agent", ""],
                "reason": "키워드 타입이 잘못된 응답입니다.",
            }
        ),
        settings=settings,
        fallback_on_error=False,
    )

    with pytest.raises(RuntimeError, match="matched_keywords 값이 유효하지 않습니다."):
        filter_.evaluate(make_document())


def test_solar_mini_llm_relevance_filter_strict_mode_rejects_missing_reason():
    settings = SolarSettings(api_key="test-key", mini_model="solar-mini-test")
    filter_ = SolarMiniLLMRelevanceFilter(
        client=FakeSolarJsonClient(
            {
                "is_relevant": True,
                "score": 0.7,
                "matched_keywords": ["agent"],
            }
        ),
        settings=settings,
        fallback_on_error=False,
    )

    with pytest.raises(RuntimeError, match="reason 값이 유효하지 않습니다."):
        filter_.evaluate(make_document())


def test_solar_mini_llm_relevance_filter_uses_fallback_for_non_finite_score():
    client = FakeSolarJsonClient(
        {
            "is_relevant": True,
            "score": "NaN",
            "matched_keywords": ["agent"],
            "reason": "점수가 유효하지 않은 응답입니다.",
        }
    )
    settings = SolarSettings(api_key="test-key", mini_model="solar-mini-test")
    filter_ = SolarMiniLLMRelevanceFilter(client=client, settings=settings)

    document = make_document()
    decision = filter_.evaluate(document)
    fallback = filter_.fallback_filter.evaluate(document)

    assert decision.score == fallback.score
