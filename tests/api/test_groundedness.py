from fastapi.testclient import TestClient

from app.api.groundedness import get_chroma
from app.main import app


class FakeChroma:
    def get_texts_by_document_ids(self, document_ids):
        assert document_ids == ["doc_001"]
        return ["LangGraph orchestrates agent workflows with graph state."]


def test_groundedness_api_returns_score():
    client = TestClient(app)
    response = client.post(
        "/api/v1/groundedness/check",
        json={
            "answer": "LangGraph orchestrates agent workflows.",
            "contexts": ["LangGraph orchestrates agent workflows with graph state."],
            "threshold": 0.5,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["score"] >= 0.5


def test_groundedness_api_uses_source_document_ids():
    app.dependency_overrides[get_chroma] = lambda: FakeChroma()
    try:
        client = TestClient(app)
        response = client.post(
            "/api/v1/groundedness/check",
            json={
                "answer": "LangGraph orchestrates agent workflows.",
                "source_document_ids": ["doc_001"],
                "threshold": 0.5,
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["data"]["score"] >= 0.5
