"""The two data shapes the desk hands to the platform (contracts section 3)."""

from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

SubscriberType = Literal["free", "paid", "comp", "gift", "group_seat", "founding", "lifetime"]


class SubscriberRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    email: str
    type: SubscriberType
    plan_interval: Literal["month", "year"] | None
    paid_until: AwareDatetime | None
    since: AwareDatetime | None

    @field_validator("email")
    @classmethod
    def _clean_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        parts = cleaned.split("@")
        if any(c.isspace() or not c.isprintable() for c in cleaned):
            raise ValueError("not an email address")
        if len(parts) != 2 or not parts[0] or not parts[1]:
            raise ValueError("not an email address")
        return cleaned

    @property
    def is_paid(self) -> bool:
        return self.type != "free"


class DirectoryListing(BaseModel):
    model_config = ConfigDict(frozen=True)

    records: list[SubscriberRecord]
    complete: bool
    rejected_rows: int = Field(ge=0)
    exported_at: AwareDatetime

    @field_validator("records")
    @classmethod
    def _paying_only(cls, value: list[SubscriberRecord]) -> list[SubscriberRecord]:
        if any(not r.is_paid for r in value):
            raise ValueError("a listing holds paying readers only")
        return value
