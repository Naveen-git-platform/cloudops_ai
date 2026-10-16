import logging
from collections.abc import Iterator
from typing import Any

from sqlalchemy import Engine, create_engine, event, inspect, make_url
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry

from app.db.base import Base

logger = logging.getLogger(__name__)


class Database:
    """Owns the engine and session factory for one running app."""

    def __init__(self, url: str, *, echo: bool = False, connect_timeout: int = 5) -> None:
        options: dict[str, Any] = {"echo": echo, "pool_pre_ping": True}
        if make_url(url).get_backend_name() == "postgresql":
            # Fail fast (and surface as a retryable 503) when the database is unreachable,
            # and don't queue for a pooled connection longer than OTLP clients wait.
            options |= {"connect_args": {"connect_timeout": connect_timeout}, "pool_timeout": 10}
        self.engine: Engine = create_engine(url, **options)
        if self.engine.dialect.name == "sqlite":
            # SQLite (test fallback only) needs foreign keys switched on per connection.
            event.listen(self.engine, "connect", _enable_sqlite_foreign_keys)
        self._sessionmaker = sessionmaker(self.engine, expire_on_commit=False)

    def create_tables(self) -> None:
        """Create missing tables directly from the models (SQLite and throwaway databases only).

        PostgreSQL schemas are managed by Alembic (`alembic upgrade head`); tables
        created this way have no migration history and need `alembic stamp head`.
        """
        if self.engine.dialect.name == "postgresql":
            logger.warning(
                "DATABASE_AUTO_CREATE is creating PostgreSQL tables outside Alembic; "
                "use `alembic upgrade head` instead (or `alembic stamp head` afterwards)"
            )
        Base.metadata.create_all(self.engine)

    def verify_schema(self) -> None:
        """Refuse to start if existing tables don't match the models.

        Catches a database that hasn't been migrated (or an old table that
        `create_all` skipped) before it breaks writes at request time. If the
        database can't be reached, startup continues: requests then get 503s
        until it's back, which is the intended outage behaviour.
        """
        try:
            problems = schema_problems(self.engine)
            unversioned = self.engine.dialect.name == "postgresql" and not inspect(self.engine).has_table(
                "alembic_version"
            )
        except (OperationalError, InterfaceError) as error:
            logger.warning("Database unreachable at startup; schema not verified: %s", error)
            return
        if problems:
            raise SchemaMismatchError(
                "Database schema doesn't match the application: "
                + "; ".join(problems)
                + ". Run `alembic upgrade head` from the backend directory."
            )
        if unversioned:
            logger.warning(
                "PostgreSQL schema matches the models but has no Alembic version; "
                "run `alembic stamp head` once so future migrations apply"
            )

    def session(self) -> Iterator[Session]:
        with self._sessionmaker() as session:
            yield session

    def dispose(self) -> None:
        self.engine.dispose()


class SchemaMismatchError(RuntimeError):
    """An existing table is missing columns or indexes the application needs."""


def schema_problems(engine: Engine) -> list[str]:
    """Columns and indexes defined in the models but missing from existing tables."""
    inspector = inspect(engine)
    problems = []
    for table in Base.metadata.sorted_tables:
        if not inspector.has_table(table.name):
            problems.append(f"table {table.name} is missing")
            continue
        existing_columns = {column["name"] for column in inspector.get_columns(table.name)}
        missing_columns = sorted(column.name for column in table.columns if column.name not in existing_columns)
        if missing_columns:
            problems.append(f"{table.name} is missing column(s) {', '.join(missing_columns)}")
        existing_indexes = {index["name"]: index for index in inspector.get_indexes(table.name)}
        for index in table.indexes:
            found = existing_indexes.get(index.name)
            if found is None:
                problems.append(f"{table.name} is missing index {index.name}")
            elif index.unique and not found["unique"]:
                problems.append(f"{table.name} index {index.name} is not unique")
    return problems


def _enable_sqlite_foreign_keys(dbapi_connection: DBAPIConnection, _: ConnectionPoolEntry) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
