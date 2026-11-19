from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings, read from PLATFORM_* environment variables."""

    model_config = SettingsConfigDict(env_prefix="PLATFORM_")

    app_mode: Literal["api", "hooks"] = "api"
    env: Literal["local", "dev", "prod"] = "local"
    gcp_project: str = "local"
    service_name: str = "platform-api"
    events_topic: str = "platform.events"
    inbound_topic: str = "inbound.webhooks"
    push_audience: str = ""
    push_service_account: str = ""
