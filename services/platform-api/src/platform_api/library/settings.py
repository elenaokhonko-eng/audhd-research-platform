from pydantic_settings import BaseSettings, SettingsConfigDict


class LibrarySettings(BaseSettings):
    """Settings of the library, read from PLATFORM_* environment variables."""

    model_config = SettingsConfigDict(env_prefix="PLATFORM_")

    library_bucket: str = ""
    library_staging_bucket: str = ""
