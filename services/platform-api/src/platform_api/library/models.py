"""Library items: the owner's manifest (item.yaml) and the stored record."""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator

Kind = Literal["meta_review", "evidence_map", "clinician_one_pager", "guide", "worksheet"]
ItemAccess = Literal["paid", "free_members", "purchase_only"]
ItemStatus = Literal["draft", "published", "retired"]

SKU = re.compile(r"^[a-z0-9][a-z0-9-]{1,58}[a-z0-9]$")
VERSION = re.compile(r"^\d+\.\d+$")


def version_key(version: str) -> tuple[int, int]:
    """Numeric order of a version: 1.10 comes after 1.9."""
    major, minor = version.split(".")
    return int(major), int(minor)


class _ItemFields(BaseModel):
    """The fields a manifest and a stored record share."""

    sku: str
    title: str
    kind: Kind
    abstract: str
    version: str
    access: ItemAccess
    status: ItemStatus
    series: str | None = None
    topics: list[str] = []
    audience: list[str] = []
    evidence_status: str | None = None
    language: str = "en"
    pages: int = 0
    cover: str | None = None
    payhip: dict[str, str] | None = None
    price_display: str | None = None
    citation: str | None = None
    related_urls: list[str] = []

    @field_validator("sku")
    @classmethod
    def _sku(cls, value: str) -> str:
        if not SKU.fullmatch(value):
            raise ValueError(
                "use 3 to 60 lower-case letters, digits and hyphens, "
                "starting and ending with a letter or digit"
            )
        return value

    @field_validator("version")
    @classmethod
    def _version(cls, value: str) -> str:
        if not VERSION.fullmatch(value):
            raise ValueError("write it as two numbers with a dot, for example 1.0")
        return value

    @field_validator("payhip")
    @classmethod
    def _payhip(cls, value: dict[str, str] | None) -> dict[str, str] | None:
        if value is not None and "url" in value and not value["url"].startswith("https://"):
            raise ValueError("url must start with https://")
        return value

    @field_validator("related_urls")
    @classmethod
    def _related_urls(cls, value: list[str]) -> list[str]:
        if any(not url.startswith("https://") for url in value):
            raise ValueError("every address must start with https://")
        return value


class Manifest(_ItemFields):
    """An item.yaml. Keys it does not know are refused."""

    model_config = ConfigDict(extra="forbid")

    file: str

    @field_validator("file")
    @classmethod
    def _file(cls, value: str) -> str:
        if "/" in value or "\\" in value:
            raise ValueError("give the bare name of a file in the item's folder")
        if not value.endswith(".pdf"):
            raise ValueError("the name must end with .pdf")
        return value


class StoredFile(BaseModel):
    bucket: str
    object: str
    sha256: str
    bytes: int


class LibraryItem(_ItemFields):
    """The stored record: the manifest's fields, its `file` kept as `file_name`."""

    file_name: str
    file: StoredFile
    published_at: datetime | None
    updated_at: datetime
    updated_by: str


class ItemOutcome(BaseModel):
    sku: str
    action: Literal["created", "new_version", "updated", "unchanged", "refused"]
    problems: list[str]


class PublishReport(BaseModel):
    dry_run: bool
    staging_prefix: str
    items: list[ItemOutcome]


class ItemCard(BaseModel):
    """What a member sees on the shelf. Nothing here says where the file is."""

    sku: str
    title: str
    kind: Kind
    abstract: str
    version: str
    pages: int
    access: ItemAccess
    can_open: bool
    buy_url: str | None


class ItemDetail(BaseModel):
    item: ItemCard
    description: str
    citation: str | None
