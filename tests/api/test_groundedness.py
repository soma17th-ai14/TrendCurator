from fastapi.testclient import TestClient

from app.main import app


def test_groundedness_api_returns_score():
    client = TestClient(app)
    response = client.post(
        "/groundedness/check",
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
