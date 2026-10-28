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
from alembic.script import ScriptDirectory
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


def old_style_database(conn):
    """Build the schema the pre-Alembic way, missing one nullable column, and add rows."""
    Base.metadata.create_all(conn)
    conn.execute(text('ALTER TABLE itineraries DROP COLUMN currency'))
    conn.execute(text(
        "INSERT INTO users (id, username, email, hashed_password) "
        "VALUES (1, 'sam', 'sam@example.com', 'x')"
    ))
    conn.execute(text(
        "INSERT INTO hotspots (id, google_place_id, name) VALUES (1, 'ChIJabc', 'Test Bistro')"
    ))
    conn.execute(text("INSERT INTO user_hotspots (user_id, hotspot_id) VALUES (1, 1)"))
    conn.execute(text(
        "INSERT INTO itineraries (id, user_id, title, destination, budget, items) "
        "VALUES (1, 1, 'Night out', 'Tokyo', '$$', '[]')"
    ))
    conn.commit()


def row_counts(conn):
    tables = ["users", "hotspots", "user_hotspots", "itineraries"]
    return {table: conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() for table in tables}


def at_head(conn):
    return MigrationContext.configure(conn).get_current_heads() == (
        ScriptDirectory.from_config(alembic_config(conn)).get_current_head(),
    )


def test_migrating_a_pre_alembic_database_adopts_it_and_keeps_every_row(empty_db):
    old_style_database(empty_db)

    migrate(empty_db)

    assert at_head(empty_db)
    assert schema_drift(empty_db) == []
    assert row_counts(empty_db) == {"users": 1, "hotspots": 1, "user_hotspots": 1, "itineraries": 1}


def schema_snapshot(conn):
    """The tables, columns, indexes and foreign keys, as text (column types don't compare by value)."""
    inspector = inspect(conn)
    return repr({
        table: (inspector.get_columns(table), inspector.get_indexes(table), inspector.get_foreign_keys(table))
        for table in sorted(inspector.get_table_names())
    })


def test_migrating_twice_changes_nothing_the_second_time(empty_db):
    old_style_database(empty_db)
    migrate(empty_db)
    schema, rows = schema_snapshot(empty_db), row_counts(empty_db)

    migrate(empty_db)

    assert at_head(empty_db)
    assert schema_snapshot(empty_db) == schema
    assert row_counts(empty_db) == rows


def test_every_migration_can_be_downgraded_and_reapplied(empty_db):
    migrate(empty_db)

    command.downgrade(alembic_config(empty_db), "base")
    empty_db.commit()
    assert set(inspect(empty_db).get_table_names()) <= {"alembic_version"}

    migrate(empty_db)
    assert schema_drift(empty_db) == []
