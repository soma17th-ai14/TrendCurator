from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.dashboard import get_chroma, get_digest_store
from app.main import app
from app.services.digest_store import DigestStoreError


class FakeChroma:
    def __init__(self, count: int = 3) -> None:
        self._count = count

    def count(self) -> int:
        return self._count


class FakeDigestStore:
    def __init__(self, latest_digest=None) -> None:
        self._latest_digest = latest_digest

    def latest(self):
        return self._latest_digest


class FailingDigestStore:
    def latest(self):
        raise DigestStoreError("broken digest store")


def _digest(digest_id: str, digest_date: date, item_count: int):
    return SimpleNamespace(
        digest_id=digest_id,
        date=digest_date,
        item_count=item_count,
    )


def test_dashboard_returns_latest_digest_summary():
    app.dependency_overrides[get_chroma] = lambda: FakeChroma(count=7)
    app.dependency_overrides[get_digest_store] = lambda: FakeDigestStore(
        _digest("digest_20260507", date(2026, 5, 7), 4)
    )
    try:
        client = TestClient(app)
        response = client.get("/api/v1/dashboard")
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["latest_digest"] == {
        "digest_id": "digest_20260507",
        "date": "2026-05-07",
        "item_count": 4,
    }
    assert payload["data"]["collection_status"]["collected_count"] == 7


def test_dashboard_returns_null_latest_digest_when_store_is_empty():
    app.dependency_overrides[get_chroma] = lambda: FakeChroma(count=0)
    app.dependency_overrides[get_digest_store] = lambda: FakeDigestStore()
    try:
        client = TestClient(app)
        response = client.get("/api/v1/dashboard")
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["latest_digest"] is None


def test_dashboard_returns_error_when_digest_store_fails():
    app.dependency_overrides[get_chroma] = lambda: FakeChroma(count=1)
    app.dependency_overrides[get_digest_store] = lambda: FailingDigestStore()
    try:
        client = TestClient(app)
        response = client.get("/api/v1/dashboard")
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is False
    assert payload["error"]["code"] == "DASHBOARD_UNAVAILABLE"
