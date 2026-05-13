from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.api.scheduler import get_scheduler_service
from app.main import app
from app.services.scheduler import SchedulerConfig, SchedulerService, SchedulerState


SEOUL = timezone(timedelta(hours=9), name="Asia/Seoul")


def _scheduler(
    config: SchedulerConfig | None = None,
    last_run_at: datetime | None = None,
) -> SchedulerService:
    return SchedulerService(
        SchedulerState(
            config=config or SchedulerConfig(),
            last_run_at=last_run_at,
        )
    )


def test_get_scheduler_returns_current_config():
    scheduler = _scheduler(
        SchedulerConfig(enabled=True, time="9:00", timezone="Asia/Seoul", sources=("huggingface",)),
        last_run_at=datetime(2026, 5, 6, 9, 1, tzinfo=SEOUL),
    )
    app.dependency_overrides[get_scheduler_service] = lambda: scheduler
    try:
        client = TestClient(app)
        response = client.get("/api/v1/scheduler")
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["enabled"] is True
    assert payload["data"]["time"] == "09:00"
    assert payload["data"]["timezone"] == "Asia/Seoul"
    assert payload["data"]["sources"] == ["huggingface"]
    assert payload["data"]["last_run_at"] == "2026-05-06T09:01:00+09:00"
    assert payload["data"]["next_run_at"]


def test_put_scheduler_updates_config():
    scheduler = _scheduler()
    app.dependency_overrides[get_scheduler_service] = lambda: scheduler
    try:
        client = TestClient(app)
        response = client.put(
            "/api/v1/scheduler",
            json={
                "enabled": False,
                "time": "10:30",
                "timezone": "UTC",
                "sources": ["hackernews"],
            },
        )
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert payload["data"]["enabled"] is False
    assert payload["data"]["time"] == "10:30"
    assert payload["data"]["timezone"] == "UTC"
    assert payload["data"]["sources"] == ["hackernews"]
    assert scheduler.state.config.enabled is False


def test_put_scheduler_rejects_invalid_time():
    scheduler = _scheduler()
    app.dependency_overrides[get_scheduler_service] = lambda: scheduler
    try:
        client = TestClient(app)
        response = client.put(
            "/api/v1/scheduler",
            json={
                "enabled": True,
                "time": "25:00",
                "timezone": "Asia/Seoul",
                "sources": ["huggingface"],
            },
        )
    finally:
        app.dependency_overrides.clear()

    payload = response.json()
    assert response.status_code == 200
    assert payload["success"] is False
    assert payload["error"]["code"] == "SCHEDULER_ERROR"


def test_put_scheduler_rejects_unknown_source_before_service_update():
    scheduler = _scheduler()
    app.dependency_overrides[get_scheduler_service] = lambda: scheduler
    try:
        client = TestClient(app)
        response = client.put(
            "/api/v1/scheduler",
            json={
                "enabled": True,
                "time": "09:00",
                "timezone": "Asia/Seoul",
                "sources": ["unknown"],
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
