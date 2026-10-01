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
        try:
            return self._s3.get_object(Bucket=self._bucket, Key=key)["Body"].read()
        except ClientError as error:
            if _missing(error):
                raise MissingObject(key) from error
            raise

    def delete(self, key: str) -> None:
        """Delete the object; one already gone counts as deleted."""
        try:
            self._s3.delete_object(Bucket=self._bucket, Key=key)
        except ClientError as error:
            if not _missing(error):
                raise


class MissingObject(Exception):
    """No object is stored under the key."""


def _missing(error: ClientError) -> bool:
    return error.response.get("Error", {}).get("Code") in {"NoSuchKey", "404", "NotFound"}
