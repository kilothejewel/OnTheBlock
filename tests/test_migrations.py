"""
Schema migrations, tested through the migrate entry point.

Each test gets its own empty database, so it doesn't clash with the per-test
create_all/drop_all fixture: a fresh in-memory SQLite database by default, or a
throwaway schema on Postgres when OTB_TEST_DATABASE_URL points there (as in CI).
"""

import uuid

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from app.core.database import alembic_config, migrate
from app.models import Base
from tests.conftest import TEST_DATABASE_URL


@pytest.fixture
def empty_db():
    """A connection to an empty database that only this test uses."""
    if TEST_DATABASE_URL.startswith("sqlite"):
        engine = create_engine("sqlite://", poolclass=StaticPool)
        with engine.connect() as conn:
            yield conn
        engine.dispose()
        return

    schema = f"migrations_{uuid.uuid4().hex[:8]}"
    engine = create_engine(TEST_DATABASE_URL)
    with engine.connect() as conn:
        conn.execute(text(f'CREATE SCHEMA "{schema}"'))
        conn.execute(text(f'SET search_path TO "{schema}"'))
        conn.commit()
        try:
            yield conn
        finally:
            conn.rollback()
            conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
            conn.commit()
    engine.dispose()


def schema_drift(conn):
    """Differences between the database's schema and the models (empty when they match)."""
    return compare_metadata(MigrationContext.configure(conn), Base.metadata)


def test_migrating_an_empty_database_matches_the_models(empty_db):
    migrate(empty_db)

    assert schema_drift(empty_db) == []
    assert {"users", "hotspots", "user_hotspots", "itineraries"} <= set(inspect(empty_db).get_table_names())


def test_every_migration_can_be_downgraded_and_reapplied(empty_db):
    migrate(empty_db)

    command.downgrade(alembic_config(empty_db), "base")
    empty_db.commit()
    assert set(inspect(empty_db).get_table_names()) <= {"alembic_version"}

    migrate(empty_db)
    assert schema_drift(empty_db) == []
