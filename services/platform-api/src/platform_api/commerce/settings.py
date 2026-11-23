from typing import Literal, Self

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Grant = Literal["tier:paid", "status:substack_paid"]


class CommerceSettings(BaseSettings):
    """Settings of the commerce lane, read from PLATFORM_* environment variables."""

    # A refused setting's message names the rule, never the values: some identify accounts.
    model_config = SettingsConfigDict(env_prefix="PLATFORM_", hide_input_in_errors=True)

    env: Literal["local", "dev", "prod"] = "local"
    stripe_substack_application: str = ""
    stripe_test_channel_metadata: bool = False
    substack_grant_month: Grant = "status:substack_paid"
    substack_grant_year: Grant = "status:substack_paid"
    # empty, or the job's full resource name
    reconcile_job: str = Field(
        default="", pattern=r"^(projects/[^/]+/locations/[^/]+/jobs/[^/]+)?$"
    )
    roster_inbox_bucket: str = ""
    grace_days: int = Field(default=21, ge=1)

    @model_validator(mode="after")
    def _no_sandbox_marker_in_prod(self) -> Self:
        if self.env == "prod" and self.stripe_test_channel_metadata:
            raise ValueError("the sandbox channel marker is refused in prod")
        return self
