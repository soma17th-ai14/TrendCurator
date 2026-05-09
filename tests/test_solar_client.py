import json
from urllib.error import URLError

import pytest

import app.core.solar_client as solar_client_module
from app.core.settings import SolarSettings
from app.core.solar_client import SolarClient, SolarMessage


class FakeResponse:
    def __init__(self, body: dict | str):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self) -> bytes:
        if isinstance(self.body, str):
            return self.body.encode("utf-8")
        return json.dumps(self.body).encode("utf-8")


def test_solar_client_chat_text_returns_message_content(monkeypatch):
    calls = []

    def fake_urlopen(request, timeout):
        calls.append((request, timeout))
        return FakeResponse({"choices": [{"message": {"content": "응답 본문"}}]})

    monkeypatch.setattr(solar_client_module, "urlopen", fake_urlopen)
    client = SolarClient(SolarSettings(api_key="test-key"), timeout_seconds=7)

    content = client.chat_text(
        model="solar-mini-test",
        messages=[SolarMessage(role="user", content="문서")],
        temperature=0.0,
    )

    request, timeout = calls[0]
    assert content == "응답 본문"
    assert timeout == 7
    assert request.headers["Authorization"] == "Bearer test-key"


def test_solar_client_chat_json_parses_content_json(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeResponse({"choices": [{"message": {"content": '{"score": 0.7}'}}]})

    monkeypatch.setattr(solar_client_module, "urlopen", fake_urlopen)
    client = SolarClient(SolarSettings(api_key="test-key"))

    assert client.chat_json(model="solar-mini-test", messages=[]) == {"score": 0.7}


def test_solar_client_chat_json_rejects_non_object_content(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeResponse({"choices": [{"message": {"content": "[1, 2, 3]"}}]})

    monkeypatch.setattr(solar_client_module, "urlopen", fake_urlopen)
    client = SolarClient(SolarSettings(api_key="test-key"))

    with pytest.raises(RuntimeError, match="JSON 응답이 객체 형식이 아닙니다"):
        client.chat_json(model="solar-mini-test", messages=[])


def test_solar_client_rejects_malformed_response_body(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeResponse({"unexpected": []})

    monkeypatch.setattr(solar_client_module, "urlopen", fake_urlopen)
    client = SolarClient(SolarSettings(api_key="test-key"))

    with pytest.raises(RuntimeError, match="응답 형식이 올바르지 않습니다"):
        client.chat_text(model="solar-mini-test", messages=[])


def test_solar_client_rejects_non_json_response_body(monkeypatch):
    def fake_urlopen(request, timeout):
        return FakeResponse("not-json")

    monkeypatch.setattr(solar_client_module, "urlopen", fake_urlopen)
    client = SolarClient(SolarSettings(api_key="test-key"))

    with pytest.raises(RuntimeError, match="응답 본문을 JSON으로 해석할 수 없습니다"):
        client.chat_text(model="solar-mini-test", messages=[])


def test_solar_client_wraps_connection_errors(monkeypatch):
    def fake_urlopen(request, timeout):
        raise URLError("network down")

    monkeypatch.setattr(solar_client_module, "urlopen", fake_urlopen)
    client = SolarClient(SolarSettings(api_key="test-key"))

    with pytest.raises(RuntimeError, match="Solar API에 연결할 수 없습니다"):
        client.chat_text(model="solar-mini-test", messages=[])
