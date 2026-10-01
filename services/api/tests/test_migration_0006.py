"""Revision 0006: columns only older data left empty are always filled now, so they are required."""

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from emva_api.settings import Settings

SERVICE = Path(__file__).parents[1]
REQUIRED = [("training_run", "backtest_key"), ("uploaded_file", "column_facts")]


@pytest.fixture
def migrations():
    development = Settings.from_environment()
    database = f"emva_test_0006_{uuid.uuid4().hex[:12]}"
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


def nullable(engine, table: str, column: str) -> bool:
    return next(c for c in inspect(engine).get_columns(table) if c["name"] == column)["nullable"]


def test_column_facts_and_backtest_key_are_required_and_optional_again_after_a_downgrade(
    migrations,
):
    config, engine = migrations

    assert [nullable(engine, *column) for column in REQUIRED] == [False, False]

    command.downgrade(config, "0005")

    assert [nullable(engine, *column) for column in REQUIRED] == [True, True]
