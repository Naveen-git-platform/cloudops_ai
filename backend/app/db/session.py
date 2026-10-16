from collections.abc import Iterator
from typing import Any

from sqlalchemy import Engine, create_engine, event, inspect, make_url
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry

from app.db.base import Base


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
        """Create missing tables, then fail if an existing table doesn't match the models.

        `create_all` skips tables that already exist, so an older table (for example
        `telemetry_records` without `fingerprint`) would otherwise be kept and break
        writes at request time. Until migrations exist, refuse to start instead.
        """
        Base.metadata.create_all(self.engine)
        problems = schema_problems(self.engine)
        if problems:
            raise SchemaMismatchError(
                "Database schema doesn't match the application: "
                + "; ".join(problems)
                + ". Drop and recreate the affected tables (migrations aren't available yet)."
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
