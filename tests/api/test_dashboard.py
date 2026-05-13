from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.dashboard import get_chroma, get_collection_status_store, get_digest_store
from app.main import app
from app.services.digest_store import DigestStoreError


class FakeChroma:
    def __init__(self, count: int = 3, source_stats: dict | None = None, keywords: list | None = None) -> None:
        self._count = count
        self._source_stats = source_stats or {}
        self._keywords = keywords or []

    def count(self) -> int:
        return self._count

    def count_by_source(self) -> dict[str, int]:
        return self._source_stats

    def top_keywords(self, top_k: int = 10) -> list[dict]:
        return self._keywords[:top_k]


class FakeDigestStore:
    def __init__(self, latest_digest=None) -> None:
        self._latest_digest = latest_digest

    def latest(self):
        return self._latest_digest


class FakeCollectionStatusStore:
    def __init__(self, collected_at: str | None = None) -> None:
        self._collected_at = collected_at

    def load_collected_at(self) -> str | None:
        return self._collected_at


class FailingDigestStore:
    def latest(self):
        raise DigestStoreError("broken digest store")


def _digest(digest_id: str, digest_date: date, item_count: int):
    return SimpleNamespace(
        digest_id=digest_id,
        date=digest_date,
        item_count=item_count,
    )


def _override(chroma=None, digest_store=None, status_store=None):
    app.dependency_overrides[get_chroma] = lambda: chroma or FakeChroma()
    app.dependency_overrides[get_digest_store] = lambda: digest_store or FakeDigestStore()
    app.dependency_overrides[get_collection_status_store] = lambda: status_store or FakeCollectionStatusStore()


def test_dashboard_returns_latest_digest_summary():
    _override(
        chroma=FakeChroma(count=7),
        digest_store=FakeDigestStore(_digest("digest_20260507", date(2026, 5, 7), 4)),
    )
    try:
        response = TestClient(app).get("/api/v1/dashboard")
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


def test_dashboard_returns_null_latest_digest_when_store_is_empty():
    _override(chroma=FakeChroma(count=0))
    try:
        response = TestClient(app).get("/api/v1/dashboard")
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["latest_digest"] is None


def test_dashboard_returns_error_when_digest_store_fails():
    _override(chroma=FakeChroma(count=1), digest_store=FailingDigestStore())
    try:
        response = TestClient(app).get("/api/v1/dashboard")
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is False
    assert payload["error"]["code"] == "DASHBOARD_UNAVAILABLE"


def test_dashboard_returns_source_stats():
    _override(
        chroma=FakeChroma(
            count=5,
            source_stats={"huggingface": 3, "hackernews": 2},
        ),
    )
    try:
        response = TestClient(app).get("/api/v1/dashboard")
    finally:
        app.dependency_overrides.clear()

    data = response.json()["data"]
    assert data["source_stats"] == {"huggingface": 3, "hackernews": 2}
    assert data["collection_status"]["collected_count"] == 5


def test_dashboard_returns_top_tags():
    keywords = [
        {"tag": "langgraph", "count": 8},
        {"tag": "multi-agent", "count": 5},
    ]
    _override(chroma=FakeChroma(keywords=keywords))
    try:
        response = TestClient(app).get("/api/v1/dashboard")
    finally:
        app.dependency_overrides.clear()

    assert response.json()["data"]["top_tags"] == keywords


def test_dashboard_returns_last_collected_at():
    _override(status_store=FakeCollectionStatusStore("2026-05-13T09:00:00Z"))
    try:
        response = TestClient(app).get("/api/v1/dashboard")
    finally:
        app.dependency_overrides.clear()

    assert response.json()["data"]["collection_status"]["last_collected_at"] == "2026-05-13T09:00:00Z"


def test_dashboard_returns_null_last_collected_at_when_never_collected():
    _override(status_store=FakeCollectionStatusStore(None))
    try:
        response = TestClient(app).get("/api/v1/dashboard")
    finally:
        app.dependency_overrides.clear()

    assert response.json()["data"]["collection_status"]["last_collected_at"] is None
