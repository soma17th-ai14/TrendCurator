"""환경변수 기반 설정 로더."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    solar_api_key: str
    solar_base_url: str = "https://api.upstage.ai/v1"
    solar_mini_model: str = "solar-mini"
    solar_pro2_model: str = "solar-pro2"
    solar_embedding_query_model: str = "embedding-query"
    solar_embedding_passage_model: str = "embedding-passage"
    chroma_data_path: str = "./chroma_data"
    chroma_collection_name: str = "trendcurator"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


def get_settings() -> Settings:
    return Settings()
