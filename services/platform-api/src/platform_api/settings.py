from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


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
    # The identity provider refuses session cookies shorter than a day or longer than 14 days.
    session_ttl_days: int = Field(default=14, ge=1, le=14)
    # PLATFORM_OWNER_ACCOUNTS=id1,id2 (comma-separated, not JSON).
    owner_accounts: Annotated[list[str], NoDecode] = []
    contact_key: str = ""
    library_bucket: str = ""

    @field_validator("owner_accounts", mode="before")
    @classmethod
    def _split_accounts(cls, value: object) -> object:
        if isinstance(value, str):
            return [part.strip() for part in value.split(",") if part.strip()]
        return value
