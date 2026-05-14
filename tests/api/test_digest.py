from datetime import date
from types import SimpleNamespace

from fastapi.testclient import TestClient

import app.api.digest as digest_api
from app.api.digest import get_digest_store, get_profile_store
from app.api.documents import get_retriever
from app.core.models import DigestGenerationRunResult, DigestItem, SolarProDigestGenerationResult
from app.main import app
from app.services.digest_retriever import DigestSearchResult


class FakeRetriever:
    def search(self, **kwargs):
        return [
            DigestSearchResult(
                document_id="doc_001",
                source="huggingface",
                title="LangGraph workflow",
                url="https://example.com/langgraph",
                content="LangGraph orchestrates agent workflows.",
                summary_preview="LangGraph workflow summary",
                similarity_score=0.9,
                relevance_score=0.9,
                published_at=date(2026, 5, 6),
                matched_keywords=["langgraph"],
                tags=["agent"],
            )
        ]


class FakeDigestStore:
    def __init__(self, results=None) -> None:
        self.saved = []
        self.results = results or {}

    def save(self, result):
        self.saved.append(result)
        self.results[result.digest_id] = result
        return result

    def get(self, digest_id):
        return self.results.get(digest_id)

    def list(self, *, date_from=None, date_to=None):
        results = list(self.results.values())
        filtered = []
        for result in results:
            if date_from is not None and result.date < date_from:
                continue
            if date_to is not None and result.date > date_to:
                continue
            filtered.append(result)
        return sorted(filtered, key=lambda item: item.date, reverse=True)


class FakeGroundednessChecker:
    def check(self, request):
        return SimpleNamespace(score=0.91)


class FakeProfileStore:
    def __init__(self, profile=None) -> None:
        self._profile = profile

    def load(self):
        return self._profile


def _run_result(digest_date: date = date(2026, 5, 6)) -> DigestGenerationRunResult:
    digest_id = f"digest_{digest_date:%Y%m%d}"
    digest = SolarProDigestGenerationResult(
        digest_id=digest_id,
        date=digest_date,
        title="AI Agent Daily Digest",
        groundedness_score=0.91,
        items=[
            DigestItem(
                document_id="doc_001",
                title="LangGraph workflow",
                source="huggingface",
                url="https://example.com/langgraph",
                published_at=digest_date,
                summary="핵심 요약",
                key_points=["핵심 내용"],
                contribution="주요 기여",
                benchmark="명시된 근거 없음",
                critique="명시된 근거 없음",
                tags=["agent"],
                evidence_document_ids=["doc_001"],
            )
        ],
    )
    return DigestGenerationRunResult(
        digest_id=digest_id,
        date=digest_date,
        item_count=1,
        candidate_count=1,
        selected_candidate_count=1,
        source_document_ids=["doc_001"],
        groundedness_score=0.91,
        digest=digest,
    )


def test_generate_digest_saves_run_result(monkeypatch):
    """엔드포인트가 regenerate_digest 를 호출해 결과를 저장하고 응답으로 돌려준다."""
    store = FakeDigestStore({"digest_20260506": _run_result()})

    calls = []

    def fake_regenerate(run_date, *, sources, keywords, language, top_k):
        calls.append({
            "run_date": run_date,
            "sources": sources,
            "keywords": keywords,
            "language": language,
            "top_k": top_k,
        })
        return f"digest_{run_date:%Y%m%d}"

    monkeypatch.setattr(digest_api, "regenerate_digest", fake_regenerate)
    app.dependency_overrides[get_digest_store] = lambda: store
    app.dependency_overrides[get_profile_store] = lambda: FakeProfileStore()
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/digest/generate",
            json={"date": "2026-05-06", "top_k": 1, "profile_based": False},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert len(calls) == 1
    assert calls[0]["run_date"] == date(2026, 5, 6)
    assert calls[0]["top_k"] == 1
    assert set(calls[0]["sources"]) == {"huggingface", "hackernews"}


def test_generate_digest_uses_profile_keywords_when_profile_based(monkeypatch):
    """profile_based=True 면 프로필의 keywords/language 가 regenerate_digest 로 전달된다."""
    from app.services.profile_store import UserProfile

    store = FakeDigestStore({"digest_20260506": _run_result()})
    captured = {}

    def fake_regenerate(run_date, *, sources, keywords, language, top_k):
        captured["keywords"] = keywords
        captured["language"] = language
        return f"digest_{run_date:%Y%m%d}"

    monkeypatch.setattr(digest_api, "regenerate_digest", fake_regenerate)

    profile = UserProfile(keywords=["AgentBench", "ToolUse"], language="en", digest_time="09:00")
    app.dependency_overrides[get_digest_store] = lambda: store
    app.dependency_overrides[get_profile_store] = lambda: FakeProfileStore(profile)
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/digest/generate",
            json={"date": "2026-05-06", "top_k": 1, "profile_based": True},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert captured["keywords"] == ["AgentBench", "ToolUse"]
    assert captured["language"] == "en"


def test_get_digest_returns_saved_digest_contract():
    store = FakeDigestStore({"digest_20260506": _run_result()})
    app.dependency_overrides[get_digest_store] = lambda: store
    try:
        client = TestClient(app)
        response = client.get("/api/v1/digest/digest_20260506")
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["digest_id"] == "digest_20260506"
    assert payload["data"]["items"][0]["document_id"] == "doc_001"


def test_get_digest_returns_error_for_missing_digest():
    app.dependency_overrides[get_digest_store] = lambda: FakeDigestStore()
    try:
        client = TestClient(app)
        response = client.get("/api/v1/digest/digest_20260506")
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is False
    assert payload["error"]["code"] == "DIGEST_NOT_FOUND"


def test_list_digests_returns_summary_items_with_date_filter():
    store = FakeDigestStore({
        "digest_20260505": _run_result(date(2026, 5, 5)),
        "digest_20260506": _run_result(date(2026, 5, 6)),
    })
    app.dependency_overrides[get_digest_store] = lambda: store
    try:
        client = TestClient(app)
        response = client.get("/api/v1/digest?date_from=2026-05-06&date_to=2026-05-06")
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert [item["digest_id"] for item in payload["data"]] == ["digest_20260506"]
    assert payload["data"][0]["item_count"] == 1
