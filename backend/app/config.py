from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

SERVICE_NAME = "cloudops-api"
VERSION = "0.1.0"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")
    database_url: str
    supabase_url: str | None = None
    database_echo: bool = False
    database_auto_create: bool = False
    database_connect_timeout: int = Field(default=5, gt=0)
    otlp_max_body_bytes: int = Field(default=10 * 1024 * 1024, gt=0)

@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
