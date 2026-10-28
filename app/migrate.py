"""Migrate the database in OTB_DATABASE_URL to the latest schema: python -m app.migrate"""

from app.core.database import migrate

if __name__ == "__main__":
    migrate()
