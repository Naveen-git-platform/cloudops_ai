"""The telemetry schema (fingerprint column and unique index) and startup schema checks."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Index, MetaData, Table, insert, inspect
from sqlalchemy.exc import IntegrityError

from app.config import Settings
from app.db import Database
from app.db.session import SchemaMismatchError, schema_problems
from app.main import create_app
from app.telemetry.models import TelemetryRecord
from app.telemetry.otlp import Signal

TABLE = TelemetryRecord.__table__


def _row(fingerprint: str) -> dict:
    now = datetime.now(UTC)
    return {
        "signal": Signal.LOGS,
        "service_name": "checkout-api",
        "timestamp": now,
        "received_at": now,
        "fingerprint": fingerprint,
        "resource_attributes": {},
        "attributes": {},
        "raw": {},
    }


def _replace_table(database: Database, *, drop_column: str | None = None, unique_fingerprint: bool = True) -> None:
    """Swap telemetry_records for an older variant, as an existing database might have it."""
    TABLE.drop(database.engine)
    old = Table(TABLE.name, MetaData(), *(column._copy() for column in TABLE.columns if column.name != drop_column))
    for index in TABLE.indexes:
        if all(column.name in old.c for column in index.columns):
            unique = index.unique and (unique_fingerprint or index.name != "uq_telemetry_fingerprint")
            Index(index.name, *(old.c[column.name] for column in index.columns), unique=unique)
    old.create(database.engine)


def test_fresh_schema_has_fingerprint_column_and_unique_index(database: Database):
    inspector = inspect(database.engine)
    fingerprint = next(c for c in inspector.get_columns("telemetry_records") if c["name"] == "fingerprint")
    assert fingerprint["nullable"] is False
    indexes = {index["name"]: index for index in inspector.get_indexes("telemetry_records")}
    assert indexes["uq_telemetry_fingerprint"]["column_names"] == ["fingerprint"]
    assert indexes["uq_telemetry_fingerprint"]["unique"]
    assert schema_problems(database.engine) == []


def test_database_enforces_fingerprint_uniqueness(database: Database):
    with database.engine.begin() as connection:
        connection.execute(insert(TABLE), _row("a" * 64))
    with database.engine.begin() as connection, pytest.raises(IntegrityError):
        connection.execute(insert(TABLE), _row("a" * 64))
    with database.engine.begin() as connection:
        connection.execute(insert(TABLE), _row("b" * 64))  # a different fingerprint is fine


def test_old_table_without_fingerprint_is_refused(database: Database):
    _replace_table(database, drop_column="fingerprint")

    with pytest.raises(SchemaMismatchError) as error:
        database.verify_schema()
    message = str(error.value)
    assert "alembic upgrade head" in message
    assert "telemetry_records is missing column(s) fingerprint" in message
    assert "missing index uq_telemetry_fingerprint" in message


def test_non_unique_fingerprint_index_is_refused(database: Database):
    _replace_table(database, unique_fingerprint=False)
    assert schema_problems(database.engine) == ["telemetry_records index uq_telemetry_fingerprint is not unique"]


def test_app_does_not_start_on_an_incompatible_table(settings: Settings, database: Database):
    _replace_table(database, drop_column="fingerprint")
    with pytest.raises(SchemaMismatchError), TestClient(create_app(settings)):
        pass


def test_app_starts_and_creates_a_fresh_schema(settings: Settings, database: Database):
    TABLE.drop(database.engine)
    with TestClient(create_app(settings.model_copy(update={"database_auto_create": True}))) as client:
        assert client.get("/telemetry/records").json() == []
    assert schema_problems(database.engine) == []
