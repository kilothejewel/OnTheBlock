from typing import Dict, List, Literal, Optional

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LOCAL_DEV_ORIGIN_REGEX = r"^http://(localhost|127\.0\.0\.1|\[::1\]):\d+$"


def with_postgres_driver(url: str) -> str:
    """
    Name psycopg2 in a Postgres URL that doesn't name a driver.

    Hosting providers hand out "postgres://" URLs, which SQLAlchemy 2 rejects.
    A bare "postgresql://" means whichever driver SQLAlchemy defaults to
    (psycopg 3 from SQLAlchemy 2.1), not the one in requirements.txt. A URL
    that names its driver, and any other database, is left alone.
    """
    for scheme in ("postgres://", "postgresql://"):
        if url.startswith(scheme):
            return "postgresql+psycopg2://" + url[len(scheme):]
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
    # One key per Google Cloud project (#44), so each project's console quota
    # is a real backstop: Places quotas are per method, not per SKU. Unset
    # (local dev), both fall back to GOOGLE_PLACES_API_KEY. The matching job's
    # key (#120) is a GitHub Actions secret and never on the API host.
    GOOGLE_LIVE_KEY: Optional[str] = None  # otb-live: Place Details 30/day, live checks (#93)
    GOOGLE_DISPLAY_KEY: Optional[str] = None  # otb-display: details (#29), photos, Discover search

    #LLM providers (app/services/llm.py, ADR 0006): free tiers only.
    # Tried in order; "rules" needs no model and never fails, so it's always last.
    LLM_CHAIN: str = "gemini,groq,rules"
    LLM_TIMEOUT_SECONDS: float = 20
    GEMINI_API_KEY: Optional[str] = None  # AI Studio key on a project without billing (#44)
    GEMINI_API_REVISION: str = "2026-05-20"  # Interactions API revision
    GEMINI_INTAKE_MODEL: str = "gemini-3.5-flash-lite"
    GEMINI_COMPOSE_MODEL: str = "gemini-3.6-flash"
    # The unpaid Gemini API may not serve users in the EEA, the UK or Switzerland.
    GEMINI_BLOCKED_COUNTRIES: str = (
        "AT,BE,BG,HR,CY,CZ,DK,EE,FI,FR,DE,GR,HU,IE,IT,LV,LT,LU,MT,NL,PL,PT,RO,SK,SI,ES,SE,IS,LI,NO,GB,CH"
    )
    GROQ_API_KEY: Optional[str] = None  # Groq free plan (#44)
    GROQ_INTAKE_MODEL: str = "openai/gpt-oss-20b"  # supports strict JSON schema output
    GROQ_COMPOSE_MODEL: str = "openai/gpt-oss-120b"

    #Free-quota guard (app/services/quota.py)
    # Per resource: "day" is a limit for all pools together, "month" for all
    # pools together split between them (see QUOTA_POOL_CAPS). A missing limit
    # means count only. Each sits just under the provider's free allowance, so
    # the provider-side caps (#44) are only a backstop. Free allowances change:
    # set OTB_QUOTA_LIMITS (JSON) rather than editing code. A resource ending
    # in ".*" covers every resource with that prefix, e.g. each LLM model.
    QUOTA_LIMITS: Dict[str, Dict[str, int]] = {
        "google.details_enterprise": {"day": 30, "month": 950},  # free cap 1,000 a month
        "google.details_pro": {"day": 160, "month": 4750},  # free cap 5,000 a month
        "google.photos": {"day": 30, "month": 950},  # Place Details Photos; free cap 1,000
        "google.text_search_enterprise": {"day": 30, "month": 900},  # Discover search (#127, #128)
        "google.text_ids": {"day": 1000},  # free and uncapped; stops runaway loops
        "llm.gemini.*": {"day": 200},  # requests a day per model
        "llm.groq.*": {"day": 500},  # requests a day per model
    }
    # Monthly caps for the pools other than "users", per resource. "users" gets
    # the rest of the monthly limit, so these pools can never eat into it. A
    # pool with no cap for a resource that has a monthly limit can't use it.
    QUOTA_POOL_CAPS: Dict[str, Dict[str, int]] = {
        "eval": {"google.details_enterprise": 200, "google.details_pro": 200},  # #108
        "guests": {"google.details_enterprise": 150, "google.details_pro": 300, "google.photos": 150},  # #125
    }

    #Briefs (app/schemas/brief.py): the most a Brief may budget, per currency.
    BUDGET_MAX: Dict[str, int] = {"ZAR": 50_000, "USD": 3_000, "GBP": 2_500, "JPY": 450_000}

    #Places catalogue ingest (scripts/catalogue/ingest.py, #119)
    CATALOGUE_MIN_CONFIDENCE: float = 0.5  # drop Overture rows less likely to exist than this

    #Per-user limits (app/core/rate_limit.py, app/services/plan_quota.py)
    PLANS_PER_USER_PER_DAY: int = 5  # new Plans a signed-in user can start per UTC day
    GUEST_PLANS_PER_DAY: int = 2  # the lower daily quota for guest users (#125)

    #Logging and error tracking (app/core/observability.py)
    LOG_FORMAT: Literal["text", "json"] = "text"  # json on Render: one JSON object per line
    LOG_LEVEL: str = "INFO"
    SENTRY_DSN: Optional[str] = None  # error tracking is off while unset
    SENTRY_ENVIRONMENT: str = "production"

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
        self.DATABASE_URL = with_postgres_driver(self.DATABASE_URL)
        return self

    model_config = SettingsConfigDict(
        env_prefix="OTB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )

settings = Settings()
