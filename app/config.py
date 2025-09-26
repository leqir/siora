from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import AnyUrl

class Settings(BaseSettings):
    SECRET_KEY: str

    DATABASE_URL: AnyUrl

    FRONTEND_URL: str
    BACKEND_URL: str

    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str  # e.g. http://localhost:8000/auth/google/callback

    OPENAI_API_KEY: str | None = None

    DEFAULT_TIMEZONE: str = "Australia/Sydney"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

settings = Settings()
