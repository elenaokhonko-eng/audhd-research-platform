import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


class PublishingDisabled(RuntimeError):
    pass


@dataclass(slots=True)
class PublicationPackage:
    title: str
    subtitle: str
    markdown: str
    artifact_paths: list[str]
    snapshot_hash: str


def build_publication_package(title: str, subtitle: str, markdown: str, artifact_paths: list[str]) -> PublicationPackage:
    canonical = json.dumps(
        {"title": title, "subtitle": subtitle, "markdown": markdown, "artifacts": sorted(artifact_paths)},
        sort_keys=True,
        separators=(",", ":"),
    )
    return PublicationPackage(title, subtitle, markdown, artifact_paths, hashlib.sha256(canonical.encode()).hexdigest())


class ManualSubstackAdapter:
    """Supported fallback while Substack offers no confirmed public write API contract."""

    def export_draft(self, package: PublicationPackage, directory: Path) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        markdown_path = directory / "substack_draft.md"
        markdown_path.write_text(f"# {package.title}\n\n_{package.subtitle}_\n\n{package.markdown}", encoding="utf-8")
        manifest = directory / "publication_manifest.json"
        manifest.write_text(json.dumps(asdict(package), indent=2, sort_keys=True), encoding="utf-8")
        return markdown_path

    def publish(self, package: PublicationPackage, approved_snapshot_hash: str, enabled: bool) -> None:
        if not enabled:
            raise PublishingDisabled("Automated Substack publishing is disabled")
        if package.snapshot_hash != approved_snapshot_hash:
            raise PublishingDisabled("Approved snapshot does not match the publication package")
        raise PublishingDisabled("No confirmed official Substack write API is configured; use the exported draft")
