"""Request bodies of the owner's routes. A body that holds an address never repeats it."""

from typing import Self

from pydantic import (
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    field_validator,
    model_validator,
)

from platform_api.entitlements.public import Campaign


class SearchBody(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    email: str = Field(repr=False)


class GrantBody(BaseModel):
    """A grant name the store accepts, and exactly one end: `months` from now, or a date
    `valid_until`."""

    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)

    email: str = Field(repr=False)
    grant: str
    months: int | None = Field(default=None, ge=1)
    valid_until: AwareDatetime | None = None
    reason: str = Field(min_length=1)

    @field_validator("grant")
    @classmethod
    def _a_grant_name(cls, grant: str) -> str:
        """`tier:paid` or `item:<sku>`, checked before any contact is made for the address."""
        if grant != "tier:paid" and not (grant.startswith("item:") and grant[5:].strip()):
            raise ValueError("a grant is tier:paid or item:<sku>")
        return grant

    @model_validator(mode="after")
    def _one_end(self) -> Self:
        if (self.months is None) == (self.valid_until is None):
            raise ValueError("give exactly one of months and valid_until")
        return self


class RevokeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1)


class CampaignsBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    campaigns: list[Campaign]


class LaunchBody(BaseModel):
    """Any subset of the owner's switches. Only the fields given are sent on (`exclude_unset`).

    The defaults are never stored: a field left out is not set, and an explicit null is refused.
    """

    model_config = ConfigDict(extra="forbid")

    join_open: StrictBool = False
    library_open: StrictBool = False
    promotions_open: StrictBool = False
    required_terms_version: str = ""
    required_privacy_version: str = ""
    reconcile_max_age_seconds: int = Field(default=900, ge=0)
    substack_account_url: str = ""

    @model_validator(mode="after")
    def _not_empty(self) -> Self:
        if not self.model_fields_set:
            raise ValueError("name at least one setting")
        return self
