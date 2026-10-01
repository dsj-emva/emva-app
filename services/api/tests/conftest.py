"""API tests run against real Postgres and object storage (compose locally, containers in CI).

Each test session gets its own database and bucket, so it never touches development data.
"""

import dataclasses
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import boto3
import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from emva_api.clock import FixedClock
from emva_api.main import create_app
from emva_api.settings import Settings

SERVICE = Path(__file__).parents[1]


@pytest.fixture(scope="session")
def settings() -> Iterator[Settings]:
    with _own_database_and_bucket() as settings:
        yield settings


@pytest.fixture
def own_settings() -> Iterator[Settings]:
    """A database and bucket of the test's own, for a test that must see everything stored."""
    with _own_database_and_bucket() as settings:
        yield settings


@pytest.fixture
def own_bucket(own_settings: Settings):
    return _bucket(own_settings)


@contextmanager
def _own_database_and_bucket() -> Iterator[Settings]:
    development = Settings.from_environment()
    run = uuid.uuid4().hex[:12]
    database = f"emva_test_{run}"
    admin = create_engine(development.database_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{database}"'))
    settings = dataclasses.replace(
        development,
        database_url=development.database_url.set(database=database),
        object_storage_bucket=f"emva-test-{run}",
    )
    migrations = Config(SERVICE / "alembic.ini")
    migrations.attributes["database_url"] = settings.database_url
    command.upgrade(migrations, "head")

    yield settings

    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE "{database}" WITH (FORCE)'))
    admin.dispose()
    bucket = _bucket(settings)
    bucket.objects.all().delete()
    bucket.delete()


@pytest.fixture
def bucket(settings: Settings):
    """The test session's bucket, read directly to check what the service stored."""
    return _bucket(settings)


def _bucket(settings: Settings):
    return boto3.resource(
        "s3",
        endpoint_url=settings.object_storage_endpoint,
        region_name=settings.object_storage_region,
        aws_access_key_id=settings.object_storage_access_key,
        aws_secret_access_key=settings.object_storage_secret_key,
    ).Bucket(settings.object_storage_bucket)


@pytest.fixture
def clock() -> FixedClock:
    return FixedClock(datetime(2026, 9, 14, 10, 0, tzinfo=UTC))


@pytest.fixture
def client(settings: Settings, clock: FixedClock) -> Iterator[TestClient]:
    with TestClient(create_app(settings, clock)) as client:
        yield client
