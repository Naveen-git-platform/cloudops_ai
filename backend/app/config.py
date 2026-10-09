from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_NAME = "cloudops-api"
VERSION = "0.1.0"


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # SQLAlchemy URL, e.g. postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
    database_url: str
    # Log every SQL statement (local debugging only).
    database_echo: bool = False
    # Create missing tables on startup. Will be replaced by migrations.
    database_auto_create: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
