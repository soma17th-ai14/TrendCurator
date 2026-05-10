import pytest

from app.core.settings import get_solar_settings


def test_get_solar_settings_requires_api_key(monkeypatch):
    monkeypatch.delenv("SOLAR_API_KEY", raising=False)
    monkeypatch.setattr("app.core.settings.load_dotenv", lambda *args, **kwargs: None)

    with pytest.raises(RuntimeError, match="SOLAR_API_KEY"):
        get_solar_settings()


def test_get_solar_settings_loads_environment(monkeypatch):
    monkeypatch.setenv("SOLAR_API_KEY", "test-key")
    monkeypatch.setenv("SOLAR_BASE_URL", "https://example.com/v1")
    monkeypatch.setenv("SOLAR_MINI_MODEL", "mini-test")
    monkeypatch.setenv("SOLAR_DIGEST_MODEL", "digest-test")

    settings = get_solar_settings()

    assert settings.api_key == "test-key"
    assert settings.base_url == "https://example.com/v1"
    assert settings.mini_model == "mini-test"
    assert settings.digest_model == "digest-test"
