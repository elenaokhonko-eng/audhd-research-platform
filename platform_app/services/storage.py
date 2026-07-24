import hashlib
from dataclasses import dataclass

import boto3

from platform_app.settings import Settings


@dataclass(slots=True)
class StoredObject:
    bucket: str
    key: str
    sha256: str
    size: int


class ArtifactStorage:
    def __init__(self, settings: Settings):
        self.bucket = settings.artifact_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.artifact_endpoint,
            region_name=settings.aws_region,
            aws_access_key_id=settings.aws_access_key_id,
            aws_secret_access_key=settings.aws_secret_access_key,
        )

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except self.client.exceptions.ClientError:
            self.client.create_bucket(Bucket=self.bucket)

    def put(self, key: str, content: bytes, content_type: str, metadata: dict[str, str] | None = None) -> StoredObject:
        digest = hashlib.sha256(content).hexdigest()
        object_metadata = {"sha256": digest, **(metadata or {})}
        self.client.put_object(
            Bucket=self.bucket,
            Key=key,
            Body=content,
            ContentType=content_type,
            Metadata=object_metadata,
            ServerSideEncryption="AES256",
        )
        return StoredObject(self.bucket, key, digest, len(content))

    def get(self, key: str) -> bytes:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
