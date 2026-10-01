from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from emva_api.records import Base
from emva_api.settings import Settings

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Tests pass the URL of their own database; otherwise it comes from the environment.
url = config.attributes.get("database_url") or Settings.from_environment().database_url

with create_engine(url).connect() as connection:
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()
