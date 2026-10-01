"""Revision 0003 downgrades cleanly, and refuses clearly once a raw file has been deleted."""

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text

from emva_api.settings import Settings

SERVICE = Path(__file__).parents[1]


@pytest.fixture
def migrations():
    development = Settings.from_environment()
    database = f"emva_test_downgrade_{uuid.uuid4().hex[:12]}"
    admin = create_engine(development.database_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{database}"'))
    url = development.database_url.set(database=database)
    config = Config(SERVICE / "alembic.ini")
    config.attributes["database_url"] = url
    command.upgrade(config, "head")
    engine = create_engine(url)
    yield config, engine
    engine.dispose()
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE "{database}" WITH (FORCE)'))
    admin.dispose()


def add_uploaded_file(engine, object_key: str | None) -> None:
    advertiser = uuid.uuid4()
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO advertiser (id, name, data_source, created_at) "
                "VALUES (:id, 'Savanna Journeys', 'hand_made_test', now())"
            ),
            {"id": advertiser},
        )
        connection.execute(
            text(
                "INSERT INTO uploaded_file (id, advertiser_id, kind, file_name, object_key, "
                "uploaded_at, row_count, column_names) VALUES (:id, :advertiser, 'leads', "
                "'leads.csv', :key, now(), 1, '[]')"
            ),
            {"id": uuid.uuid4(), "advertiser": advertiser, "key": object_key},
        )


def test_downgrading_below_0003_works_while_every_raw_file_is_kept(migrations):
    config, engine = migrations
    add_uploaded_file(engine, "advertisers/a/leads/1.csv")

    command.downgrade(config, "0002")


def test_downgrading_below_0003_is_refused_once_a_raw_file_was_deleted(migrations):
    config, engine = migrations
    add_uploaded_file(engine, None)

    with pytest.raises(RuntimeError, match="Cannot downgrade below 0003"):
        command.downgrade(config, "0002")
