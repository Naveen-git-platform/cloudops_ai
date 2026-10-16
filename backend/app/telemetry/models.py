from datetime import datetime
from typing import Any

from sqlalchemy import JSON, BigInteger, Enum, Float, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, UTCDateTime
from app.telemetry.otlp import Signal

# JSONB on PostgreSQL (indexable, compact); plain JSON elsewhere (SQLite test fallback).
JsonDocument = JSON().with_variant(JSONB(), "postgresql")


class TelemetryRecord(Base):
    """One span, metric data point or log record, normalised from OTLP.

    Common fields are columns for filtering; everything else (attributes and
    the raw OTLP record) is kept as JSON for correlation and investigation.
    """

    __tablename__ = "telemetry_records"
    __table_args__ = (
        Index("ix_telemetry_service_time", "service_name", "timestamp"),
        Index("ix_telemetry_service_signal_time", "service_name", "signal", "timestamp"),
        Index("ix_telemetry_trace_id", "trace_id"),
        # Makes ingestion idempotent: an exact resend of a record is ignored.
        Index("uq_telemetry_fingerprint", "fingerprint", unique=True),
    )

    id: Mapped[int] = mapped_column(BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True)
    signal: Mapped[Signal] = mapped_column(
        Enum(
            Signal,
            name="ck_telemetry_signal",
            native_enum=False,
            length=16,
            values_callable=lambda members: [m.value for m in members],
            create_constraint=True,
        )
    )

    # Resource (who emitted it)
    service_name: Mapped[str] = mapped_column(String(255))
    service_namespace: Mapped[str | None] = mapped_column(String(255))
    service_version: Mapped[str | None] = mapped_column(String(255))
    environment: Mapped[str | None] = mapped_column(String(255))
    host_name: Mapped[str | None] = mapped_column(String(255))
    scope_name: Mapped[str | None] = mapped_column(String(255))
    scope_version: Mapped[str | None] = mapped_column(String(255))

    # When
    timestamp: Mapped[datetime] = mapped_column(UTCDateTime())
    end_timestamp: Mapped[datetime | None] = mapped_column(UTCDateTime())
    received_at: Mapped[datetime] = mapped_column(UTCDateTime())

    # Span name, metric name or log event name
    name: Mapped[str | None] = mapped_column(String(1024))

    # Trace context (spans, and logs that carry it)
    trace_id: Mapped[str | None] = mapped_column(String(32))
    span_id: Mapped[str | None] = mapped_column(String(16))
    parent_span_id: Mapped[str | None] = mapped_column(String(16))
    span_kind: Mapped[str | None] = mapped_column(String(16))
    status_code: Mapped[str | None] = mapped_column(String(16))

    # Logs
    severity_number: Mapped[int | None] = mapped_column(Integer)
    severity_text: Mapped[str | None] = mapped_column(String(32))
    body: Mapped[str | None] = mapped_column(Text)

    # Metrics
    metric_type: Mapped[str | None] = mapped_column(String(32))
    unit: Mapped[str | None] = mapped_column(String(64))
    value: Mapped[float | None] = mapped_column(Float)

    # SHA-256 of signal, resource, scope and raw record (see normalize.fingerprint).
    fingerprint: Mapped[str] = mapped_column(String(64))

    resource_attributes: Mapped[dict[str, Any]] = mapped_column(JsonDocument)
    attributes: Mapped[dict[str, Any]] = mapped_column(JsonDocument)
    raw: Mapped[dict[str, Any]] = mapped_column(JsonDocument)
