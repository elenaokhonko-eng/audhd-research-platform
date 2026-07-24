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
    ncbi_api_key: str | None = None
    openalex_api_key: str | None = None
    research_contact_email: str | None = None
    embedding_api_key: str | None = None
    embedding_base_url: str | None = None
    embedding_model: str = "text-embedding-3-small"
    oidc_required: bool = False
    admin_emails: str = ""
    local_auth_email: str = "local@example.invalid"
    substack_publication_url: str | None = None
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    trusted_auth_proxy: bool = False
    api_base_url: str = "http://localhost:8000"


@lru_cache
def get_settings() -> Settings:
    return Settings()
