from pathlib import Path
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

ALEMBIC_INI = Path(__file__).resolve().parents[2] / "alembic.ini"

# Create database engine
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
engine = create_engine(
    settings.DATABASE_URL,
    # pool_pre_ping checks connection liveness on checkout
    pool_pre_ping=True,
    # SQLite (local dev / tests) needs this to be usable across FastAPI's threads
    connect_args={"check_same_thread": False} if _is_sqlite else {},
)

# Create SessionLocal class for database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative base class for models
Base = declarative_base()

# The first migration: what a database built by create_all before Alembic is adopted at.
BASELINE_REVISION = "0001"

def alembic_config(conn: Connection):
    """Alembic config that runs migrations on an open connection (read by migrations/env.py)."""
    # Imported here: the migration environment imports the models, which import this module.
    from alembic.config import Config

    config = Config(str(ALEMBIC_INI))
    config.attributes["connection"] = conn
    return config

def migrate(bind=engine) -> None:
    """
    Bring the database's schema up to the latest migration.

    A database built before Alembic (app tables but no alembic_version) is
    adopted first: it gets any nullable columns it's missing, then is stamped
    at the baseline, so the upgrade only runs the migrations after it.

    The only thing that changes the schema: run by `python -m app.migrate`,
    locally and before the API starts on Render (render.yaml). Takes an
    engine or an open connection, and commits when done.
    """
    from alembic import command

    # Put every table on Base.metadata before it's read below. `python -m
    # app.migrate` imports only this module, and with no models loaded a
    # pre-Alembic database looks empty, so the baseline would try to create
    # tables that exist. Imported here: the models import this module.
    import app.models  # noqa: F401

    if not isinstance(bind, Connection):
        with bind.connect() as conn:
            migrate(conn)
        return

    config = alembic_config(bind)
    if _is_pre_alembic(bind):
        _add_missing_columns(bind)
        command.stamp(config, BASELINE_REVISION)
    command.upgrade(config, "head")
    bind.commit()

def _is_pre_alembic(conn: Connection) -> bool:
    """Whether the database has app tables but no alembic_version (built with create_all)."""
    inspector = inspect(conn)
    if inspector.has_table("alembic_version"):
        return False
    return any(inspector.has_table(table.name) for table in Base.metadata.sorted_tables)

# The baseline migration's (0001) columns. A database built before Alembic is
# brought up to exactly these before it's stamped at the baseline; anything a
# later migration adds is left to that migration.
BASELINE_COLUMNS = {
    "users": {"id", "username", "email", "hashed_password", "is_active", "created_at", "supabase_uid"},
    "hotspots": {"id", "google_place_id", "name", "rating", "user_rating_count", "address", "latitude",
                 "longitude", "price_level", "types", "created_at"},
    "itineraries": {"id", "user_id", "title", "destination", "budget", "duration_days", "city", "currency",
                    "items", "created_at"},
    "user_hotspots": {"user_id", "hotspot_id", "created_at"},
}


def _add_missing_columns(conn: Connection) -> None:
    """
    Add the baseline's nullable columns that an existing table lacks, with
    their indexes.

    create_all() never altered existing tables, so a database built with it
    can be missing columns added to the models before migrations existed.
    This brings it up to the baseline (BASELINE_COLUMNS) before it's stamped
    there, and never adds a column a later migration owns.
    """
    inspector = inspect(conn)
    for table in Base.metadata.sorted_tables:
        baseline = BASELINE_COLUMNS.get(table.name)
        if baseline is None or not inspector.has_table(table.name):
            continue
        existing = {column["name"] for column in inspector.get_columns(table.name)}
        added = set()
        for column in table.columns:
            if column.name in baseline and column.name not in existing and column.nullable:
                column_type = column.type.compile(dialect=conn.dialect)
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}'))
                added.add(column.name)
        for index in table.indexes:
            if {column.name for column in index.columns} & added:
                index.create(conn)

def get_db():
    """Dependency to get a local database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
