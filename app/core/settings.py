"""Application settings loaded from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class SolarSettings:
    api_key: str
    base_url: str = "https://api.upstage.ai/v1"
    mini_model: str = "solar-mini"
    pro2_model: str = "solar-pro2"


def get_solar_settings() -> SolarSettings:
    """Load Solar settings from environment variables.

    API keys must be injected through the runtime environment or a local
    untracked .env loader. This function does not read files directly.
    """

    api_key = os.environ.get("SOLAR_API_KEY")
    if not api_key:
        raise RuntimeError("SOLAR_API_KEY 환경변수가 설정되지 않았습니다.")

    return SolarSettings(
        api_key=api_key,
        base_url=os.environ.get("SOLAR_BASE_URL", SolarSettings.base_url),
        mini_model=os.environ.get("SOLAR_MINI_MODEL", SolarSettings.mini_model),
        pro2_model=os.environ.get("SOLAR_PRO2_MODEL", SolarSettings.pro2_model),
    )
