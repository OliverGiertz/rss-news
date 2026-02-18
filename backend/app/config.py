from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import AliasChoices, Field
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

    wordpress_base_url: str | None = Field(default=None, validation_alias=AliasChoices("WORDPRESS_BASE_URL", "WP_BASE_URL"))
    wordpress_username: str | None = Field(default=None, validation_alias=AliasChoices("WORDPRESS_USERNAME", "WP_USERNAME"))
    wordpress_app_password: str | None = Field(default=None, validation_alias=AliasChoices("WORDPRESS_APP_PASSWORD", "WP_PASSWORD"))
    wordpress_default_status: str = "draft"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    # Prefer shared legacy env from the original rss-news workspace if present.
    env_candidates = (
        Path("/Users/oliver/Documents/rss-news/.env"),
        Path("backend/.env"),
        Path(".env"),
    )
    for env_path in env_candidates:
        if env_path.exists():
            load_dotenv(env_path, override=False)
    return Settings()
