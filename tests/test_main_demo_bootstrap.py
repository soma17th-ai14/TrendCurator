from app import main as app_main
from app.services.scheduler import SchedulerConfig


def test_demo_bootstrap_not_spawned_when_env_is_disabled(monkeypatch):
    monkeypatch.delenv("DEMO_BOOTSTRAP_ON_STARTUP", raising=False)

    assert app_main._maybe_spawn_demo_bootstrap_on_startup(SchedulerConfig()) is None


def test_demo_bootstrap_spawns_with_configured_days(monkeypatch):
    config = SchedulerConfig(sources=("huggingface",))
    calls = []
    fake_thread = object()

    def fake_spawn(received_config, days):
        calls.append((received_config, days))
        return fake_thread

    monkeypatch.setenv("DEMO_BOOTSTRAP_ON_STARTUP", "1")
    monkeypatch.setenv("DEMO_BOOTSTRAP_DAYS", "7")
    monkeypatch.setattr(app_main, "_spawn_demo_bootstrap_thread", fake_spawn)

    result = app_main._maybe_spawn_demo_bootstrap_on_startup(config)

    assert result is fake_thread
    assert calls == [(config, 7)]


def test_demo_bootstrap_uses_default_days_for_invalid_value(monkeypatch):
    config = SchedulerConfig()
    calls = []

    monkeypatch.setenv("DEMO_BOOTSTRAP_ON_STARTUP", "true")
    monkeypatch.setenv("DEMO_BOOTSTRAP_DAYS", "not-a-number")
    monkeypatch.setattr(
        app_main,
        "_spawn_demo_bootstrap_thread",
        lambda received_config, days: calls.append((received_config, days)) or object(),
    )

    app_main._maybe_spawn_demo_bootstrap_on_startup(config)

    assert calls == [(config, 5)]


def test_demo_bootstrap_skips_when_days_is_negative(monkeypatch):
    monkeypatch.setenv("DEMO_BOOTSTRAP_ON_STARTUP", "1")
    monkeypatch.setenv("DEMO_BOOTSTRAP_DAYS", "-1")

    assert app_main._maybe_spawn_demo_bootstrap_on_startup(SchedulerConfig()) is None


def test_startup_coordinator_runs_bootstrap_then_digest_then_scheduler(monkeypatch):
    """코디네이터 스레드가 demo_bootstrap → startup_digest → ensure_loop_running 순서로
    호출하는지 검증한다. 이 순서가 지켜져야 부트스트랩 완료 전에 스케줄러 루프가 같은
    날짜 파이프라인을 트리거하는 race 가 발생하지 않는다.
    """

    class _FakeScheduler:
        def __init__(self):
            self.state = type("S", (), {"config": SchedulerConfig(sources=("huggingface",))})()

    scheduler = _FakeScheduler()
    calls: list[str] = []

    monkeypatch.setattr(
        "app.services.scheduled_pipeline.run_demo_bootstrap",
        lambda config, days: calls.append(f"bootstrap:{days}"),
    )
    monkeypatch.setattr(
        "app.services.scheduled_pipeline.run_startup_digest",
        lambda config: calls.append("startup-digest"),
    )
    monkeypatch.setattr(
        "app.api.scheduler.ensure_loop_running",
        lambda s: calls.append("ensure-loop"),
    )

    thread = app_main._spawn_startup_coordinator(scheduler, demo_days=5)
    thread.join(timeout=2.0)

    assert calls == ["bootstrap:5", "startup-digest", "ensure-loop"]


def test_startup_coordinator_skips_bootstrap_when_days_zero(monkeypatch):
    """demo_days=0 이면 부트스트랩을 건너뛰고 startup_digest → 스케줄러 순서로만 진행."""

    class _FakeScheduler:
        def __init__(self):
            self.state = type("S", (), {"config": SchedulerConfig()})()

    scheduler = _FakeScheduler()
    calls: list[str] = []

    monkeypatch.setattr(
        "app.services.scheduled_pipeline.run_demo_bootstrap",
        lambda config, days: calls.append(f"bootstrap:{days}"),  # 호출되면 안 됨
    )
    monkeypatch.setattr(
        "app.services.scheduled_pipeline.run_startup_digest",
        lambda config: calls.append("startup-digest"),
    )
    monkeypatch.setattr(
        "app.api.scheduler.ensure_loop_running",
        lambda s: calls.append("ensure-loop"),
    )

    thread = app_main._spawn_startup_coordinator(scheduler, demo_days=0)
    thread.join(timeout=2.0)

    assert calls == ["startup-digest", "ensure-loop"]


def test_startup_coordinator_still_starts_scheduler_on_bootstrap_failure(monkeypatch):
    """부트스트랩이나 startup digest 가 예외를 던져도 스케줄러 루프는 시작돼야 한다."""

    class _FakeScheduler:
        def __init__(self):
            self.state = type("S", (), {"config": SchedulerConfig()})()

    scheduler = _FakeScheduler()
    calls: list[str] = []

    def _boom_bootstrap(config, days):
        raise RuntimeError("boom")

    def _boom_digest(config):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.services.scheduled_pipeline.run_demo_bootstrap", _boom_bootstrap)
    monkeypatch.setattr("app.services.scheduled_pipeline.run_startup_digest", _boom_digest)
    monkeypatch.setattr(
        "app.api.scheduler.ensure_loop_running",
        lambda s: calls.append("ensure-loop"),
    )

    thread = app_main._spawn_startup_coordinator(scheduler, demo_days=3)
    thread.join(timeout=2.0)

    assert calls == ["ensure-loop"]
