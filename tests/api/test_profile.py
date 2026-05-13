from fastapi.testclient import TestClient

from app.api.profile import get_profile_store
from app.main import app
from app.services.profile_store import ProfileStoreError, UserProfile


class FakeProfileStore:
    def __init__(self, profile: UserProfile | None = None) -> None:
        self._profile = profile

    def load(self) -> UserProfile | None:
        return self._profile

    def save(self, profile: UserProfile) -> UserProfile:
        self._profile = profile
        return profile


class FailingProfileStore:
    def load(self) -> UserProfile | None:
        raise ProfileStoreError("broken store")

    def save(self, profile: UserProfile) -> UserProfile:
        raise ProfileStoreError("broken store")


def test_get_profile_returns_saved_profile():
    profile = UserProfile(keywords=["LangGraph", "RAG"], language="ko", digest_time="09:00")
    app.dependency_overrides[get_profile_store] = lambda: FakeProfileStore(profile)
    try:
        response = TestClient(app).get("/api/v1/profile")
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["keywords"] == ["LangGraph", "RAG"]
    assert payload["data"]["language"] == "ko"
    assert payload["data"]["digest_time"] == "09:00"


def test_get_profile_returns_error_when_not_set():
    app.dependency_overrides[get_profile_store] = lambda: FakeProfileStore(None)
    try:
        response = TestClient(app).get("/api/v1/profile")
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is False
    assert payload["error"]["code"] == "PROFILE_NOT_FOUND"


def test_get_profile_returns_error_on_store_failure():
    app.dependency_overrides[get_profile_store] = lambda: FailingProfileStore()
    try:
        response = TestClient(app).get("/api/v1/profile")
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is False
    assert payload["error"]["code"] == "PROFILE_NOT_FOUND"


def test_put_profile_saves_and_returns_message():
    store = FakeProfileStore()
    app.dependency_overrides[get_profile_store] = lambda: store
    try:
        response = TestClient(app).put(
            "/api/v1/profile",
            json={"keywords": ["AgentBench", "ToolUse"], "language": "en", "digest_time": "18:00"},
        )
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["message"] == "Profile updated"
    assert store._profile.keywords == ["AgentBench", "ToolUse"]
    assert store._profile.language == "en"
    assert store._profile.digest_time == "18:00"


def test_put_profile_returns_error_on_store_failure():
    app.dependency_overrides[get_profile_store] = lambda: FailingProfileStore()
    try:
        response = TestClient(app).put(
            "/api/v1/profile",
            json={"keywords": ["RAG"], "language": "ko", "digest_time": "09:00"},
        )
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is False
    assert payload["error"]["code"] == "PROFILE_NOT_FOUND"
