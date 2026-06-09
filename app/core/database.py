from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

# Create database engine
engine = create_engine(
    settings.DATABASE_URL,
    # pool_pre_ping checks connection liveness on checkout
    pool_pre_ping=True,
)

# Create SessionLocal class for database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative base class for models
Base = declarative_base()

def get_db():
    """Dependency to get a local database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
