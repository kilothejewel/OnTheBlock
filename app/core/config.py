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
    
    #Supabase Settings
    SUPABASE_URL: str
    SUPABASE_KEY: str
    
    #OpenAI Settings
    OPENAI_API_KEY: str
    
    #Google Places Settings
    GOOGLE_PLACES_API_KEY: str
    
    @property
    def DATABASE_URL(self):
        """Constructs the Postgres URL from individual components."""
        return f"postgresql+psycopg2://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}/{self.POSTGRES_DB}"

    model_config = SettingsConfigDict(
        #
        env_prefix="OTB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=True
    )

    settings = Settings()
