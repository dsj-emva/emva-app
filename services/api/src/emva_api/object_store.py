"""Files in S3-compatible object storage (SeaweedFS locally); nothing is kept on local disk."""

import boto3
from botocore.exceptions import ClientError

from emva_api.settings import Settings


class ObjectStore:
    def __init__(self, settings: Settings) -> None:
        self._bucket = settings.object_storage_bucket
        self._s3 = boto3.client(
            "s3",
            endpoint_url=settings.object_storage_endpoint,
            region_name=settings.object_storage_region,
            aws_access_key_id=settings.object_storage_access_key,
            aws_secret_access_key=settings.object_storage_secret_key,
        )

    def ensure_bucket(self) -> None:
        try:
            self._s3.head_bucket(Bucket=self._bucket)
        except ClientError:
            self._s3.create_bucket(Bucket=self._bucket)

    def put(self, key: str, content: bytes) -> None:
        self._s3.put_object(Bucket=self._bucket, Key=key, Body=content)

    def get(self, key: str) -> bytes:
        return self._s3.get_object(Bucket=self._bucket, Key=key)["Body"].read()

    def delete(self, key: str) -> None:
        self._s3.delete_object(Bucket=self._bucket, Key=key)
