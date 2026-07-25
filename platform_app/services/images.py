import base64
import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from openai import OpenAI

from platform_app.settings import Settings


@dataclass(slots=True)
class ImageRequest:
    purpose: str
    prompt: str
    alt_text: str
    caption: str
    evidence_label: str = "Illustrative image - not clinical evidence"


class EditorialImageGenerator:
    def __init__(self, settings: Settings):
        if not settings.image_api_key:
            raise ValueError("IMAGE_API_KEY is required for editorial image generation")
        self.model = settings.image_model
        self.client = OpenAI(api_key=settings.image_api_key, base_url=settings.image_base_url)

    def generate(self, request: ImageRequest, output_path: Path, source_artifact_hashes: list[str]) -> dict:
        safe_prompt = (
            f"{request.prompt}\n\nCreate an editorial science illustration, not a diagnostic image. "
            "Avoid identifiable patients, medical stereotyping, labels on people, or claims of biological certainty."
        )
        result = self.client.images.generate(model=self.model, prompt=safe_prompt, size="1536x1024")
        if not result.data or not result.data[0].b64_json:
            raise RuntimeError("Image provider did not return base64 image data")
        content = base64.b64decode(result.data[0].b64_json)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(content)
        digest = hashlib.sha256(content).hexdigest()
        provenance = {
            "request": asdict(request),
            "model": self.model,
            "sha256": digest,
            "source_artifact_hashes": source_artifact_hashes,
        }
        provenance_path = output_path.with_suffix(output_path.suffix + ".provenance.json")
        provenance_path.write_text(json.dumps(provenance, indent=2, sort_keys=True), encoding="utf-8")
        return {"path": str(output_path), "sha256": digest, "provenance": str(provenance_path)}
