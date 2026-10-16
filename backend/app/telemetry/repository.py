"""Reads and writes `telemetry_records`."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import Executable, String, select
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.orm import Session

from app.telemetry.models import TelemetryRecord
from app.telemetry.otlp import Signal

# VARCHAR limits per column. Longer values are clipped (the full value stays in
# `raw`/`attributes`) so one oversized field can't make PostgreSQL reject a batch.
_COLUMN_LIMITS = {
    column.name: column.type.length
    for column in TelemetryRecord.__table__.columns
    if isinstance(column.type, String) and column.type.length
}


def _insert_skipping_duplicates(dialect: str) -> Executable:
    """INSERT ... ON CONFLICT (fingerprint) DO NOTHING for the supported databases."""
    if dialect == "postgresql":
        return postgresql.insert(TelemetryRecord).on_conflict_do_nothing(index_elements=["fingerprint"])
    if dialect == "sqlite":
        return sqlite.insert(TelemetryRecord).on_conflict_do_nothing(index_elements=["fingerprint"])
    raise RuntimeError(f"Telemetry storage doesn't support the {dialect} database")


def _fit_columns(row: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value[: _COLUMN_LIMITS[key]] if isinstance(value, str) and key in _COLUMN_LIMITS else value
        for key, value in row.items()
    }


@dataclass(frozen=True)
class TelemetryQuery:
    service_name: str | None = None
    signal: Signal | None = None
    start: datetime | None = None
    end: datetime | None = None
    trace_id: str | None = None
    limit: int = 100


class TelemetryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def add_many(self, rows: list[dict[str, Any]]) -> int:
        """Insert normalised rows in one transaction, skipping exact duplicates.

        Duplicates (same fingerprint) within the batch or already stored are
        ignored, which makes client retries safe. Returns the number of distinct
        records submitted; how many of those were already stored isn't reported,
        because counting them (RETURNING) halves bulk insert throughput.
        """
        unique = {row["fingerprint"]: _fit_columns(row) for row in rows}
        if not unique:
            return 0
        stmt = _insert_skipping_duplicates(self._session.get_bind().dialect.name)
        # Core executemany (not the ORM bulk path): the fastest batched insert for both drivers.
        self._session.connection().execute(stmt, list(unique.values()))
        self._session.commit()
        return len(unique)

    def query(self, q: TelemetryQuery) -> Sequence[TelemetryRecord]:
        """Records matching all given filters, newest first. `start` is inclusive, `end` exclusive."""
        stmt = select(TelemetryRecord)
        if q.service_name is not None:
            stmt = stmt.where(TelemetryRecord.service_name == q.service_name)
        if q.signal is not None:
            stmt = stmt.where(TelemetryRecord.signal == q.signal)
        if q.start is not None:
            stmt = stmt.where(TelemetryRecord.timestamp >= q.start)
        if q.end is not None:
            stmt = stmt.where(TelemetryRecord.timestamp < q.end)
        if q.trace_id is not None:
            stmt = stmt.where(TelemetryRecord.trace_id == q.trace_id.lower())
        stmt = stmt.order_by(TelemetryRecord.timestamp.desc(), TelemetryRecord.id.desc()).limit(q.limit)
        return self._session.scalars(stmt).all()
