from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, text

from emva_api.records import Base
from emva_api.settings import Settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Tests pass the URL of their own database; otherwise it comes from the environment.
url = config.attributes.get("database_url") or Settings.from_environment().database_url

# Every replica of the service migrates on start. The lock makes them take turns: each one reads
# the database's revision only once it holds the lock, so the first migrates and the rest find
# nothing to do. It is released when the migration's transaction ends.
MIGRATION_LOCK = 7_265_401

with create_engine(url).connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        connection.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": MIGRATION_LOCK})
        context.run_migrations()
