from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str = "postgresql+psycopg://audhd:audhd@localhost:5432/audhd"
    redis_url: str = "redis://localhost:6379/0"
    artifact_bucket: str = "audhd-artifacts"
    artifact_endpoint: str | None = "http://localhost:9000"
    aws_region: str = "ap-southeast-1"
    require_deidentified_clinical_data: bool = True
    substack_publish_enabled: bool = False


@lru_cache
def get_settings() -> Settings:
    return Settings()
