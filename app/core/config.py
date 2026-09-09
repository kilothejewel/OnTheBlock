from typing import Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    #Core Settings
    PROJECT_NAME: str ="OnTheBlock"
    VERSION: str ="1.0.0"
    API_V1_STR: str ="/api/v1"

    #Database Settings
    POSTGRES_SERVER: str
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    # Optional full SQLAlchemy URL. When set (OTB_DATABASE_URL), it overrides the
    # POSTGRES_* components above -- useful for SQLite in local dev / tests.
    DATABASE_URL: Optional[str] = None

    #Supabase Settings
    SUPABASE_URL: str
    SUPABASE_KEY: str

    #OpenAI Settings
    OPENAI_API_KEY: str

    #Google Places Settings
    GOOGLE_PLACES_API_KEY: str

    #Auth / JWT Settings
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    @model_validator(mode="after")
    def _assemble_database_url(self) -> "Settings":
        """Build the Postgres URL from components unless an explicit URL was given."""
        if not self.DATABASE_URL:
            self.DATABASE_URL = (
                f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
                f"@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"
            )
        return self

    model_config = SettingsConfigDict(
        env_prefix="OTB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )

settings = Settings()
