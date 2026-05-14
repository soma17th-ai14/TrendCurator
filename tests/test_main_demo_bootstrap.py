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
