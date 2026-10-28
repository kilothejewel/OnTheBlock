"""
Alembic environment.

The database comes from the app's settings (OTB_DATABASE_URL), unless the
caller hands over an open connection in config.attributes["connection"], as
app.core.database.migrate does. Batch mode is on so column changes also work
on SQLite, which can't ALTER most things in place.
"""

from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine

from app.core.config import settings
from app.models import Base

config = context.config

# Only set up logging when run from the alembic CLI, so tests and the app keep
# their own logging.
if config.config_file_name is not None and "connection" not in config.attributes:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    """Print the SQL instead of running it (alembic upgrade --sql)."""
    context.configure(
        url=settings.DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
elif "connection" in config.attributes:
    run_migrations(config.attributes["connection"])
else:
    engine = create_engine(settings.DATABASE_URL)
    with engine.connect() as connection:
        run_migrations(connection)
    engine.dispose()
