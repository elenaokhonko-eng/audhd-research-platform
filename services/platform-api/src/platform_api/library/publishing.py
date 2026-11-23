"""Publishing: items move from a folder of the staging bucket into the library bucket.

Each item is published or refused by itself. A stored file is never overwritten:
a changed file needs a new version.
"""

import hashlib
import re
from datetime import datetime
from typing import Any, Literal

import yaml
from pydantic import ValidationError
from pydantic_core import ErrorDetails

from platform_api.library.models import (
    ItemOutcome,
    LibraryItem,
    Manifest,
    PublishReport,
    StoredFile,
    version_key,
)
from platform_api.library.runtime import get_runtime
from platform_api.library.settings import LibrarySettings
from platform_api.shared.events import new_event

STAGING_PREFIX = re.compile(r"^[a-z0-9-]{1,40}$")

# The fields of a record that do not come from the manifest.
_NOT_FROM_MANIFEST = {"file", "published_at", "updated_at", "updated_by"}

_Action = Literal["created", "new_version", "updated", "unchanged"]


class _Refused(Exception):
    def __init__(self, *problems: str) -> None:
        self.problems = list(problems)


def parse_manifest(text: str) -> tuple[Manifest | None, list[str]]:
    """Read an item.yaml. Problems are worded as "<field>: <what is wrong>"."""
    try:
        data: Any = yaml.safe_load(text)
    except yaml.YAMLError:
        return None, ["item.yaml: not valid YAML"]
    if not isinstance(data, dict):
        return None, ["item.yaml: expected a list of fields such as `sku: ...`"]
    if isinstance(data.get("version"), float):
        return None, ['version: write it in quotes, for example "1.10"']
    try:
        return Manifest.model_validate(data), []
    except ValidationError as error:
        return None, [_problem(e) for e in error.errors()]


def _problem(error: ErrorDetails) -> str:
    field = ".".join(str(part) for part in error["loc"]) or "item.yaml"
    message = str(error["msg"]).removeprefix("Value error, ")
    return f"{field}: {message}"


def publish(staging_prefix: str, dry_run: bool, actor: str, now: datetime) -> PublishReport:
    if not STAGING_PREFIX.fullmatch(staging_prefix):
        raise ValueError("staging_prefix: use 1 to 40 lower-case letters, digits and hyphens")
    runtime = get_runtime()
    outcomes = []
    for folder in sorted(runtime.staging.list_dirs(staging_prefix)):
        try:
            outcomes.append(_publish_one(staging_prefix, folder, dry_run, actor, now))
        except _Refused as refused:
            outcomes.append(ItemOutcome(sku=folder, action="refused", problems=refused.problems))
    return PublishReport(dry_run=dry_run, staging_prefix=staging_prefix, items=outcomes)


def _publish_one(prefix: str, folder: str, dry_run: bool, actor: str, now: datetime) -> ItemOutcome:
    runtime = get_runtime()
    raw = runtime.staging.read(f"{prefix}/{folder}/item.yaml")
    if raw is None:
        raise _Refused("item.yaml: missing")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise _Refused("item.yaml: not UTF-8 text") from None
    manifest, problems = parse_manifest(text)
    if manifest is None:
        raise _Refused(*problems)
    if manifest.sku != folder:
        raise _Refused(f"sku: the folder is named {folder}")

    src = f"{prefix}/{folder}/{manifest.file}"
    content = runtime.staging.read(src)
    if content is None:
        raise _Refused(f"file: {manifest.file} is not in the folder")
    if not content.startswith(b"%PDF"):
        raise _Refused(f"file: {manifest.file} is not a PDF")
    sha = hashlib.sha256(content).hexdigest()
    dst = f"items/{manifest.sku}/{manifest.version}/{manifest.file}"

    stored = runtime.items.get(manifest.sku)
    item = LibraryItem(
        **manifest.model_dump(exclude={"file"}),
        file_name=manifest.file,
        file=StoredFile(
            bucket=LibrarySettings().library_bucket, object=dst, sha256=sha, bytes=len(content)
        ),
        published_at=_published_at(stored, manifest, now),
        updated_at=now,
        updated_by=actor,
    )
    action = _action(stored, item)
    outcome = ItemOutcome(sku=folder, action=action, problems=[])
    if action == "unchanged":
        return outcome

    if runtime.files.exists(dst) and runtime.files.sha256(dst) != sha:
        raise _Refused("file: other content is already stored for this version")
    if dry_run:
        return outcome
    copied = runtime.files.create_from(runtime.staging, src, dst)
    if not copied and runtime.files.sha256(dst) != sha:
        raise _Refused("file: other content is already stored for this version")
    runtime.items.put(item)

    becomes_published = stored is None or stored.status != "published" or action == "new_version"
    if item.status == "published" and becomes_published:
        runtime.bus.publish(
            new_event(
                "content.item.published",
                f"library:{item.sku}",
                {
                    "content_id": f"library:{item.sku}",
                    "source": "library",
                    "access": item.access,
                    "sku": item.sku,
                    "version": item.version,
                },
                now=now,
            )
        )
    return outcome


def _published_at(stored: LibraryItem | None, manifest: Manifest, now: datetime) -> datetime | None:
    if stored is not None and stored.published_at is not None:
        return stored.published_at
    return now if manifest.status == "published" else None


def _action(stored: LibraryItem | None, item: LibraryItem) -> _Action:
    if stored is None:
        return "created"
    new, old = version_key(item.version), version_key(stored.version)
    if new > old:
        return "new_version"
    if new < old:
        raise _Refused(f"version: {item.version} is older than the published {stored.version}")
    if item.file.sha256 != stored.file.sha256:
        raise _Refused(
            f"version: {item.version} is already published with different content; "
            "raise the version"
        )
    same = item.model_dump(exclude=_NOT_FROM_MANIFEST) == stored.model_dump(
        exclude=_NOT_FROM_MANIFEST
    )
    return "unchanged" if same else "updated"
