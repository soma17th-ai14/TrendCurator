"""앱 부팅 시 ChromaDB 청소 옵션 (CHROMA_RESET_ON_STARTUP) 동작 테스트."""

from __future__ import annotations

import pytest

from app import main as app_main


class _FakeChromaClient:
    instances: list["_FakeChromaClient"] = []

    def __init__(self, settings) -> None:
        self.settings = settings
        self.reset_called = 0
        _FakeChromaClient.instances.append(self)

    def reset_collection(self) -> None:
        self.reset_called += 1


@pytest.fixture(autouse=True)
def _reset_instances():
    _FakeChromaClient.instances.clear()
    yield
    _FakeChromaClient.instances.clear()


def test_reset_runs_when_env_truthy(monkeypatch):
    monkeypatch.setenv("CHROMA_RESET_ON_STARTUP", "1")
    monkeypatch.setattr("app.core.chroma_client.ChromaClient", _FakeChromaClient)

    app_main._maybe_reset_chroma_on_startup()

    assert len(_FakeChromaClient.instances) == 1
    assert _FakeChromaClient.instances[0].reset_called == 1


@pytest.mark.parametrize("value", ["0", "false", "no", ""])
def test_reset_skipped_when_env_falsy(monkeypatch, value):
    monkeypatch.setenv("CHROMA_RESET_ON_STARTUP", value)
    monkeypatch.setattr("app.core.chroma_client.ChromaClient", _FakeChromaClient)

    app_main._maybe_reset_chroma_on_startup()

    assert _FakeChromaClient.instances == []


def test_reset_failure_is_swallowed(monkeypatch):
    """청소 중 예외가 발생해도 앱 부팅 흐름을 막지 않는다."""

    class _BrokenClient:
        def __init__(self, settings) -> None:
            raise RuntimeError("chroma down")

    monkeypatch.setenv("CHROMA_RESET_ON_STARTUP", "1")
    monkeypatch.setattr("app.core.chroma_client.ChromaClient", _BrokenClient)

    # 예외를 raise 하면 안 된다.
    app_main._maybe_reset_chroma_on_startup()
