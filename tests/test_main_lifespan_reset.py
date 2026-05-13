"""앱 부팅 시 시연용 상태 청소 (CHROMA_RESET_ON_STARTUP) 동작 테스트.

청소 범위:
- 벡터DB(ChromaDB) 컬렉션
- 다이제스트 파일
- 수집 상태 파일
"""

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


class _FakeDigestStore:
    instances: list["_FakeDigestStore"] = []

    def __init__(self, path) -> None:
        self.path = path
        self.delete_all_called = 0
        _FakeDigestStore.instances.append(self)

    def delete_all(self) -> int:
        self.delete_all_called += 1
        return 3


class _FakeCollectionStatusStore:
    instances: list["_FakeCollectionStatusStore"] = []

    def __init__(self, path) -> None:
        self.path = path
        self.clear_called = 0
        _FakeCollectionStatusStore.instances.append(self)

    def clear(self) -> bool:
        self.clear_called += 1
        return True


@pytest.fixture(autouse=True)
def _reset_instances():
    _FakeChromaClient.instances.clear()
    _FakeDigestStore.instances.clear()
    _FakeCollectionStatusStore.instances.clear()
    yield
    _FakeChromaClient.instances.clear()
    _FakeDigestStore.instances.clear()
    _FakeCollectionStatusStore.instances.clear()


def _patch_all_stores(monkeypatch) -> None:
    monkeypatch.setattr("app.core.chroma_client.ChromaClient", _FakeChromaClient)
    monkeypatch.setattr("app.services.digest_store.FileDigestStore", _FakeDigestStore)
    monkeypatch.setattr(
        "app.services.collection_status_store.CollectionStatusStore",
        _FakeCollectionStatusStore,
    )


def test_reset_clears_chroma_digests_and_status_when_env_truthy(monkeypatch):
    """env 가 1 이면 벡터DB + 다이제스트 + 수집 상태가 모두 비워져야 한다."""
    monkeypatch.setenv("CHROMA_RESET_ON_STARTUP", "1")
    _patch_all_stores(monkeypatch)

    app_main._maybe_reset_state_on_startup()

    assert len(_FakeChromaClient.instances) == 1
    assert _FakeChromaClient.instances[0].reset_called == 1
    assert len(_FakeDigestStore.instances) == 1
    assert _FakeDigestStore.instances[0].delete_all_called == 1
    assert len(_FakeCollectionStatusStore.instances) == 1
    assert _FakeCollectionStatusStore.instances[0].clear_called == 1


@pytest.mark.parametrize("value", ["0", "false", "no", ""])
def test_reset_skipped_when_env_falsy(monkeypatch, value):
    """env 가 비활성이면 어떤 청소도 호출되지 않는다."""
    monkeypatch.setenv("CHROMA_RESET_ON_STARTUP", value)
    _patch_all_stores(monkeypatch)

    app_main._maybe_reset_state_on_startup()

    assert _FakeChromaClient.instances == []
    assert _FakeDigestStore.instances == []
    assert _FakeCollectionStatusStore.instances == []


def test_each_stage_is_isolated_so_failure_does_not_block_others(monkeypatch):
    """한 청소 단계가 실패해도 나머지 단계는 계속 진행돼야 한다.

    Why: 데모 시연 직전 부팅이 한 모듈의 일시적 오류로 막히면 곤란하므로 각 단계는
    독립적으로 try/except 처리된다.
    """

    class _BrokenChroma:
        def __init__(self, settings) -> None:
            raise RuntimeError("chroma down")

    monkeypatch.setenv("CHROMA_RESET_ON_STARTUP", "1")
    monkeypatch.setattr("app.core.chroma_client.ChromaClient", _BrokenChroma)
    monkeypatch.setattr("app.services.digest_store.FileDigestStore", _FakeDigestStore)
    monkeypatch.setattr(
        "app.services.collection_status_store.CollectionStatusStore",
        _FakeCollectionStatusStore,
    )

    app_main._maybe_reset_state_on_startup()

    # Chroma 가 깨졌어도 digest/status 청소는 정상 호출돼야 한다.
    assert _FakeDigestStore.instances[0].delete_all_called == 1
    assert _FakeCollectionStatusStore.instances[0].clear_called == 1
