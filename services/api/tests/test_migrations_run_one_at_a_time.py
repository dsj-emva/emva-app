"""Every replica of the service runs the migrations on start; two at once must not collide."""

import os
import subprocess
import sys
import uuid
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, text

from emva_api.settings import Settings

SERVICE = Path(__file__).parents[1]
REPLICAS = 4


def test_replicas_starting_together_migrate_the_database_once() -> None:
    development = Settings.from_environment()
    database = f"emva_test_migrations_{uuid.uuid4().hex[:12]}"
    admin = create_engine(development.database_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        connection.execute(text(f'CREATE DATABASE "{database}"'))
    url = development.database_url.set(database=database)
    try:
        environment = {
            **os.environ,
            "DATABASE_URL": url.set(drivername="postgresql").render_as_string(hide_password=False),
        }
        replicas = [
            subprocess.Popen(
                [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
                cwd=SERVICE,
                env=environment,
                stderr=subprocess.PIPE,
                text=True,
            )
            for _ in range(REPLICAS)
        ]
        outcomes = [(replica.wait(timeout=60), replica.stderr.read()) for replica in replicas]

        assert [code for code, _ in outcomes] == [0] * REPLICAS, outcomes
        head = ScriptDirectory.from_config(Config(SERVICE / "alembic.ini")).get_current_head()
        engine = create_engine(url)
        with engine.connect() as connection:
            versions = connection.execute(text("SELECT version_num FROM alembic_version")).all()
        engine.dispose()
        assert versions == [(head,)]
    finally:
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE "{database}" WITH (FORCE)'))
        admin.dispose()
