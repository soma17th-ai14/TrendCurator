"""환경변수에서 애플리케이션 설정을 읽습니다."""

from __future__ import annotations

from dataclasses import dataclass
import os
from dotenv import load_dotenv


@dataclass(frozen=True)
class SolarSettings:
    api_key: str
    base_url: str = "https://api.upstage.ai/v1"
    mini_model: str = "solar-mini"
    digest_model: str = "solar-pro3"


def get_solar_settings() -> SolarSettings:
    """환경변수에서 Solar 설정을 읽습니다.

    API 키는 런타임 환경변수 또는 커밋되지 않는 로컬 .env 로더를 통해
    주입해야 합니다. 이 함수는 파일을 직접 읽지 않습니다.
    """

    load_dotenv(".env.local")

    api_key = os.environ.get("SOLAR_API_KEY")
    if not api_key:
        raise RuntimeError("SOLAR_API_KEY 환경변수가 설정되지 않았습니다.")

    return SolarSettings(
        api_key=api_key,
        base_url=os.environ.get("SOLAR_BASE_URL", SolarSettings.base_url),
        mini_model=os.environ.get("SOLAR_MINI_MODEL", SolarSettings.mini_model),
        digest_model=os.environ.get("SOLAR_DIGEST_MODEL", SolarSettings.digest_model),
    )
