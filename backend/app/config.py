from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_NAME = "cloudops-api"
VERSION = "0.1.0"


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables or a local .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # SQLAlchemy URL, e.g. postgresql+psycopg://USER:PASSWORD@HOST:5432/DBNAME
    database_url: str
    supabase_url: str | None = None
    # Log every SQL statement (local debugging only).
    database_echo: bool = False
    # Create missing tables from the models on startup. Off by default: Alembic
    # (`alembic upgrade head`) manages the PostgreSQL schema. For SQLite and
    # throwaway local databases only.
    database_auto_create: bool = False
    # Seconds to wait when opening a database connection. Without a limit, an
    # unreachable database makes requests hang until the OS gives up (minutes).
    database_connect_timeout: int = Field(default=5, gt=0)
    # Largest accepted OTLP request body, in bytes, both as sent and after decompression.
    otlp_max_body_bytes: int = Field(default=10 * 1024 * 1024, gt=0)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]  # values come from the environment
