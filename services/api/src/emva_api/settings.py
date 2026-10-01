"""Configuration from environment variables; the defaults match compose.yaml."""

import os
from dataclasses import dataclass

from sqlalchemy.engine import URL, make_url


@dataclass(frozen=True)
class Settings:
    database_url: URL
    object_storage_endpoint: str
    object_storage_bucket: str
    object_storage_region: str
    object_storage_access_key: str
    object_storage_secret_key: str

    @classmethod
    def from_environment(cls) -> "Settings":
        env = os.environ.get
        return cls(
            database_url=postgres_url(
                env("DATABASE_URL", "postgresql://emva:emva@localhost:5433/emva")
            ),
            object_storage_endpoint=env("AWS_ENDPOINT_URL", "http://localhost:8333"),
            object_storage_bucket=env("OBJECT_STORAGE_BUCKET", "emva"),
            object_storage_region=env("AWS_DEFAULT_REGION", "us-east-1"),
            object_storage_access_key=env("AWS_ACCESS_KEY_ID", "emva"),
            object_storage_secret_key=env("AWS_SECRET_ACCESS_KEY", "emva"),
        )


def postgres_url(url: str) -> URL:
    """A Postgres URL as hosts hand it out (postgresql://...), driven by psycopg."""
    return make_url(url).set(drivername="postgresql+psycopg")
