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

def add_missing_columns(bind=engine) -> None:
    """
    Add new nullable columns to tables that already exist.

    create_all() only creates missing tables, so a column added to a model
    would never reach an existing database. This stopgap covers additive
    changes until proper migrations (Alembic) are set up.
    """
    inspector = inspect(bind)
    with bind.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {column["name"] for column in inspector.get_columns(table.name)}
            for column in table.columns:
                if column.name not in existing and column.nullable:
                    column_type = column.type.compile(dialect=bind.dialect)
                    conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{column.name}" {column_type}'))

def migrate(bind=engine) -> None:
    """
    Bring the database's schema up to the latest migration.

    The one way the schema changes: run on deploy and for local setup
    (`python -m app.migrate`). Takes an engine or an open connection, and
    commits when done.
    """
    # Imported here: the migration environment imports the models, which import this module.
    from alembic import command
    from alembic.config import Config

    if not isinstance(bind, Connection):
        with bind.connect() as conn:
            migrate(conn)
        return

    config = Config(str(ALEMBIC_INI))
    config.attributes["connection"] = bind
    command.upgrade(config, "head")
    bind.commit()

def get_db():
    """Dependency to get a local database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
