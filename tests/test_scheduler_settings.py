import pytest

from app.core.scheduler_settings import load_scheduler_config_from_env
from app.services.scheduler import SchedulerConfigError


def test_load_scheduler_config_from_env_uses_defaults() -> None:
    config = load_scheduler_config_from_env({})

    assert config.enabled is True
    assert config.time == "09:00"
    assert config.timezone == "Asia/Seoul"
    assert config.sources == ("huggingface", "hackernews")


def test_load_scheduler_config_from_env_overrides_values() -> None:
    config = load_scheduler_config_from_env(
        {
            "SCHEDULER_ENABLED": "false",
            "SCHEDULER_TIME": "18:30",
            "SCHEDULER_TIMEZONE": "UTC",
            "SCHEDULER_SOURCES": "huggingface, hackernews, custom",
        }
    )

    assert config.enabled is False
    assert config.time == "18:30"
    assert config.timezone == "UTC"
    assert config.sources == ("huggingface", "hackernews", "custom")


def test_load_scheduler_config_from_process_env_when_env_is_omitted(monkeypatch) -> None:
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("SCHEDULER_TIME", "18:30")
    monkeypatch.setenv("SCHEDULER_TIMEZONE", "UTC")
    monkeypatch.setenv("SCHEDULER_SOURCES", "huggingface,hackernews")

    config = load_scheduler_config_from_env()

    assert config.enabled is False
    assert config.time == "18:30"
    assert config.timezone == "UTC"
    assert config.sources == ("huggingface", "hackernews")


def test_load_scheduler_config_from_env_rejects_invalid_enabled() -> None:
    with pytest.raises(SchedulerConfigError):
        load_scheduler_config_from_env({"SCHEDULER_ENABLED": "maybe"})
