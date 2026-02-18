from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Prefer backend-specific env file to avoid collisions with legacy root .env
    model_config = SettingsConfigDict(
        env_file=("backend/.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_env: str = "development"
    app_name: str = "rss-news-backend"
    app_secret_key: str = "replace-with-a-long-random-secret"

    app_admin_username: str = "admin"
    app_admin_password: str = "change-me"

    session_cookie_name: str = "rss_news_session"
    session_max_age_seconds: int = 28800

    app_db_path: str = "backend/data/rss_news.db"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
