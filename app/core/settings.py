"""환경변수 기반 설정 로더."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from pydantic_settings import BaseSettings


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

    load_dotenv(".env")
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


class Settings(BaseSettings):
    solar_api_key: str = ""
    solar_base_url: str = "https://api.upstage.ai/v1"
    solar_mini_model: str = "solar-mini"
    solar_embedding_query_model: str = "embedding-query"
    solar_embedding_passage_model: str = "embedding-passage"
    chroma_data_path: str = "./chroma_data"
    chroma_collection_name: str = "trendcurator"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


def get_settings() -> Settings:
    return Settings()
