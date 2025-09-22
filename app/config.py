from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    SECRET_KEY: str
    DATABASE_URL: str

    BACKEND_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"

    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str

    OPENAI_API_KEY: str | None = None

    # cookie name for auth
    SESSION_COOKIE_NAME: str = "access_token"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 14  # 14 days

    class Config:
        env_file = ".env"


settings = Settings()
