from collections.abc import Iterator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine.interfaces import DBAPIConnection
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import ConnectionPoolEntry

from app.db.base import Base


class Database:
    """Owns the engine and session factory for one running app."""

    def __init__(self, url: str, *, echo: bool = False) -> None:
        self.engine: Engine = create_engine(url, echo=echo, pool_pre_ping=True)
        if self.engine.dialect.name == "sqlite":
            # SQLite (test fallback only) needs foreign keys switched on per connection.
            event.listen(self.engine, "connect", _enable_sqlite_foreign_keys)
        self._sessionmaker = sessionmaker(self.engine, expire_on_commit=False)

    def create_tables(self) -> None:
        Base.metadata.create_all(self.engine)

    def session(self) -> Iterator[Session]:
        with self._sessionmaker() as session:
            yield session

    def dispose(self) -> None:
        self.engine.dispose()


def _enable_sqlite_foreign_keys(dbapi_connection: DBAPIConnection, _: ConnectionPoolEntry) -> None:
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()
