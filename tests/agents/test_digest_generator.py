"""Solar Pro Digest 응답 파서 테스트."""

import json
from datetime import date

import pytest

from app.agents.digest_generator import (
    SolarProDigestGenerator,
    SolarProDigestResponseParser,
    load_solar_pro_digest_prompt,
)
from app.core.models import DigestCandidate, SolarProDigestGenerationRequest
from app.core.settings import SolarSettings


class FakeSolarTextClient:
    def __init__(self, response: str):
        self.response = response
        self.calls: list[dict] = []

    def chat_text(self, **kwargs) -> str:
        self.calls.append(kwargs)
        return self.response


class FailingSolarTextClient:
    def chat_text(self, **kwargs) -> str:
        raise RuntimeError("Solar API 요청 실패")


def _candidate(**overrides) -> DigestCandidate:
    base = {
        "document_id": "doc_001",
        "source": "huggingface",
        "title": "LangGraph Agent Workflow",
        "url": "https://huggingface.co/papers/2405.01234",
        "published_at": date(2026, 5, 5),
        "content": "A paper about LangGraph based multi-agent workflow.",
        "summary_preview": "LangGraph 기반 멀티 에이전트 워크플로우 논문이다.",
        "similarity_score": 0.87,
        "relevance_score": 0.93,
        "matched_keywords": ["langgraph", "multi-agent"],
        "tags": ["multi-agent", "workflow"],
        "metadata": {},
    }
    base.update(overrides)
    return DigestCandidate(**base)


def _request() -> SolarProDigestGenerationRequest:
    return SolarProDigestGenerationRequest(
        digest_date=date(2026, 5, 6),
        profile_keywords=["LangGraph", "Multi-agent"],
        candidates=[_candidate()],
    )


def _response_payload(**overrides) -> dict:
    base = {
        "digest_id": "digest_20260506",
        "date": "2026-05-06",
        "title": "AI Agent Daily Digest",
        "items": [
            {
                "document_id": "doc_001",
                "title": "LangGraph Agent Workflow",
                "source": "huggingface",
                "url": "https://huggingface.co/papers/2405.01234",
                "published_at": "2026-05-05",
                "summary": "LangGraph 기반 멀티 에이전트 워크플로우를 다룬다.",
                "key_points": ["워크플로우 구성", "멀티 에이전트 실행"],
                "contribution": "에이전트 워크플로우 설계 사례를 제공한다.",
                "benchmark": "명시된 근거 없음",
                "critique": "명시된 근거 없음",
                "tags": ["multi-agent", "workflow"],
                "evidence_document_ids": ["doc_001"],
                "llm_model": "solar-pro-3",
            }
        ],
        "groundedness_score": 0.0,
    }
    base.update(overrides)
    return base


def test_parse_valid_dict_response():
    parser = SolarProDigestResponseParser()

    result = parser.parse(_response_payload(), request=_request())

    assert result.digest_id == "digest_20260506"
    assert result.date == date(2026, 5, 6)
    assert result.items[0].document_id == "doc_001"
    assert result.items[0].evidence_document_ids == ["doc_001"]
    assert result.items[0].llm_model == "solar-pro-3"


def test_parse_valid_json_string_response():
    parser = SolarProDigestResponseParser()
    raw_response = json.dumps(_response_payload())

    result = parser.parse(raw_response, request=_request())

    assert result.title == "AI Agent Daily Digest"


def test_parse_rejects_invalid_json_string():
    parser = SolarProDigestResponseParser()

    with pytest.raises(ValueError, match="JSON"):
        parser.parse("not json", request=_request())


def test_parse_rejects_missing_required_item_field():
    parser = SolarProDigestResponseParser()
    payload = _response_payload()
    del payload["items"][0]["summary"]

    with pytest.raises(ValueError, match="계약"):
        parser.parse(payload, request=_request())


def test_parse_rejects_unknown_evidence_document_id():
    parser = SolarProDigestResponseParser()
    payload = _response_payload()
    payload["items"][0]["evidence_document_ids"] = ["doc_missing"]

    with pytest.raises(ValueError, match="후보 문서"):
        parser.parse(payload, request=_request())


def test_parse_rejects_unknown_item_document_id():
    parser = SolarProDigestResponseParser()
    payload = _response_payload()
    payload["items"][0]["document_id"] = "doc_missing"

    with pytest.raises(ValueError, match="후보 문서와 일치"):
        parser.parse(payload, request=_request())


def test_parse_rejects_missing_candidate_item():
    parser = SolarProDigestResponseParser()
    request = SolarProDigestGenerationRequest(
        digest_date=date(2026, 5, 6),
        profile_keywords=["LangGraph", "Multi-agent"],
        candidates=[
            _candidate(document_id="doc_001"),
            _candidate(document_id="doc_002", url="https://example.com/doc_002"),
        ],
    )
    payload = _response_payload()

    with pytest.raises(ValueError, match="후보 문서와 일치"):
        parser.parse(payload, request=request)


def test_parse_rejects_candidate_item_order_mismatch():
    parser = SolarProDigestResponseParser()
    request = SolarProDigestGenerationRequest(
        digest_date=date(2026, 5, 6),
        profile_keywords=["LangGraph", "Multi-agent"],
        candidates=[
            _candidate(document_id="doc_001"),
            _candidate(document_id="doc_002", url="https://example.com/doc_002"),
        ],
    )
    payload = _response_payload()
    second_item = dict(payload["items"][0])
    second_item["document_id"] = "doc_002"
    second_item["evidence_document_ids"] = ["doc_002"]
    payload["items"] = [second_item, payload["items"][0]]

    with pytest.raises(ValueError, match="순서"):
        parser.parse(payload, request=request)


def test_parse_rejects_empty_evidence_document_ids():
    parser = SolarProDigestResponseParser()
    payload = _response_payload()
    payload["items"][0]["evidence_document_ids"] = []

    with pytest.raises(ValueError, match="evidence_document_ids"):
        parser.parse(payload, request=_request())


def test_parse_rejects_response_date_mismatch():
    parser = SolarProDigestResponseParser()
    payload = _response_payload(date="2026-05-07")

    with pytest.raises(ValueError, match="digest_date"):
        parser.parse(payload, request=_request())


def test_parse_rejects_digest_id_mismatch():
    parser = SolarProDigestResponseParser()
    payload = _response_payload(digest_id="digest_20260507")

    with pytest.raises(ValueError, match="digest_id"):
        parser.parse(payload, request=_request())


def test_parse_rejects_wrong_llm_model():
    parser = SolarProDigestResponseParser()
    payload = _response_payload()
    payload["items"][0]["llm_model"] = "solar-mini"

    with pytest.raises(ValueError, match="llm_model"):
        parser.parse(payload, request=_request())


def test_load_solar_pro_digest_prompt_contains_output_contract():
    prompt = load_solar_pro_digest_prompt()

    assert "Solar Pro 3 Daily Digest" in prompt
    assert "evidence_document_ids" in prompt
    assert "명시된 근거 없음" in prompt
    assert "기존 기술 대비 차별점 및 한계" in prompt
    assert "일반 템플릿 문구" in prompt
    assert "groundedness_score" in prompt
    assert "항상 `0.0`" in prompt


def test_generator_calls_configured_digest_model_and_parses_response():
    client = FakeSolarTextClient(json.dumps(_response_payload(), ensure_ascii=False))
    generator = SolarProDigestGenerator(
        client=client,
        settings=SolarSettings(api_key="test-key", digest_model="solar-pro3-test"),
        system_prompt="system prompt",
    )

    result = generator.generate(_request())

    assert result.digest_id == "digest_20260506"
    assert client.calls[0]["model"] == "solar-pro3-test"
    assert client.calls[0]["temperature"] == 0.0
    assert client.calls[0]["response_format"] == {"type": "json_object"}
    assert client.calls[0]["messages"][0].role == "system"
    assert client.calls[0]["messages"][0].content == "system prompt"
    assert client.calls[0]["messages"][1].role == "user"
    user_payload = json.loads(client.calls[0]["messages"][1].content)
    assert user_payload["digest_date"] == "2026-05-06"
    assert user_payload["candidates"][0]["document_id"] == "doc_001"


def test_generator_raises_when_client_fails():
    generator = SolarProDigestGenerator(
        client=FailingSolarTextClient(),
        settings=SolarSettings(api_key="test-key", digest_model="solar-pro3-test"),
        system_prompt="system prompt",
    )

    with pytest.raises(RuntimeError, match="생성 호출"):
        generator.generate(_request())


def test_generator_raises_when_response_fails_parser_validation():
    client = FakeSolarTextClient(json.dumps(_response_payload(digest_id="digest_20260507")))
    generator = SolarProDigestGenerator(
        client=client,
        settings=SolarSettings(api_key="test-key", digest_model="solar-pro3-test"),
        system_prompt="system prompt",
    )

    with pytest.raises(ValueError, match="digest_id"):
        generator.generate(_request())
