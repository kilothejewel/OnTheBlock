from typing import List, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_DEV_ORIGIN_REGEX = r"^http://(localhost|127\.0\.0\.1|\[::1\]):\d+$"


def normalize_database_url(url: str) -> str:
    """
    Pin Postgres URLs to the psycopg2 driver this app installs. Hosts hand out
    "postgres://" or "postgresql://" URLs, and SQLAlchemy 2.1 maps a bare
    "postgresql://" to psycopg (v3), which isn't installed.
    """
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg2://" + url[len(prefix):]
    return url


class Settings(BaseSettings):
    #Core Settings
    PROJECT_NAME: str ="OnTheBlock"
    VERSION: str ="1.0.0"
    API_V1_STR: str ="/api/v1"

    #Database Settings
    # Full SQLAlchemy URL (OTB_DATABASE_URL), e.g. a hosted Postgres URL from
    # Neon or Supabase. When unset, it is built from the POSTGRES_* parts, and
    # without those the app uses a local SQLite file.
    DATABASE_URL: Optional[str] = None
    POSTGRES_SERVER: Optional[str] = None
    POSTGRES_USER: Optional[str] = None
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: Optional[str] = None

    #OpenAI Settings (optional: without a key, itineraries use demo data)
    OPENAI_API_KEY: Optional[str] = None
    OPENAI_MODEL: str = "gpt-4o-mini"

    #Google Places Settings (optional: without a key, places use demo data)
    GOOGLE_PLACES_API_KEY: Optional[str] = None

    #Auth / JWT Settings
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    #CORS Settings
    # Comma-separated list of origins allowed to call the API from a browser,
    # e.g. the live site's address in production.
    FRONTEND_ORIGINS: str = "http://localhost:5273,http://127.0.0.1:5273"
    # Optional regex for extra allowed origins. Off by default so production
    # only accepts FRONTEND_ORIGINS; local .env files set LOCAL_DEV_ORIGIN_REGEX
    # so the dev site works on any local port.
    FRONTEND_ORIGIN_REGEX: Optional[str] = None

    @property
    def frontend_origins(self) -> List[str]:
        """FRONTEND_ORIGINS parsed into a list of individual origins."""
        return [o.strip().rstrip("/") for o in self.FRONTEND_ORIGINS.split(",") if o.strip()]

    @model_validator(mode="after")
    def _assemble_database_url(self) -> "Settings":
        """Use the explicit URL, else build one from the POSTGRES_* parts, else local SQLite."""
        if not self.DATABASE_URL:
            parts = (self.POSTGRES_USER, self.POSTGRES_PASSWORD, self.POSTGRES_SERVER, self.POSTGRES_DB)
            if all(parts):
                self.DATABASE_URL = (
                    f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                    f"@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"
                )
            else:
                self.DATABASE_URL = "sqlite:///./ontheblock.db"
        self.DATABASE_URL = normalize_database_url(self.DATABASE_URL)
        return self

    model_config = SettingsConfigDict(
        env_prefix="OTB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )

settings = Settings()
