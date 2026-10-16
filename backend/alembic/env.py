"""Alembic environment: migrates the database described by the application's models.

The target URL comes from `sqlalchemy.url` when set programmatically (tests),
otherwise from the application's settings (`DATABASE_URL` env var or `.env`).
PostgreSQL is the migration target.
"""

from logging.config import fileConfig

from sqlalchemy import create_engine, pool

from alembic import context
from app.config import Settings
from app.db import Base
from app.telemetry import models as telemetry_models  # noqa: F401  # registers telemetry_records

config = context.config
if config.config_file_name is not None and config.attributes.get("configure_logging", True):
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def database_url() -> str:
    return config.get_main_option("sqlalchemy.url") or Settings().database_url  # type: ignore[call-arg]


def run_migrations_offline() -> None:
    """Emit SQL to stdout (`alembic upgrade head --sql`) instead of connecting."""
    context.configure(
        url=database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    engine = create_engine(database_url(), poolclass=pool.NullPool)
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
