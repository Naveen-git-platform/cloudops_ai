"""Pydantic models for the OTLP/JSON wire format (the subset we read).

Field names follow OTLP/JSON (lowerCamelCase). Unknown fields are kept
(`extra="allow"`) so the raw record can be stored for later analysis.
Envelopes keep records as plain dicts; each record is validated on its own so
one bad record can be rejected without failing the whole batch.
"""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field


class OtlpModel(BaseModel):
    model_config = ConfigDict(extra="allow")


def _nanos_to_datetime(value: Any) -> datetime | None:
    """OTLP timestamps are uint64 nanoseconds since the epoch (JSON: number or string). 0 means unset."""
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int | str):
        # ValueError, not TypeError: pydantic only reports ValueError as a validation error.
        raise ValueError("timestamp must be an integer number of nanoseconds")  # noqa: TRY004
    nanos = int(value)
    if not 0 <= nanos < 2**64:
        raise ValueError("timestamp must be an unsigned 64-bit integer")
    if nanos == 0:
        return None
    try:
        # Stored with microsecond precision; the exact nanoseconds remain in the raw record.
        return _EPOCH + timedelta(microseconds=nanos // 1_000)
    except OverflowError:
        raise ValueError("timestamp is out of range") from None


_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _hex_id(length: int) -> BeforeValidator:
    def validate(value: Any) -> str | None:
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ValueError("must be a hex string")  # noqa: TRY004 - see _nanos_to_datetime
        normalized = value.lower()
        if len(normalized) != length or any(c not in "0123456789abcdef" for c in normalized):
            raise ValueError(f"must be {length} hex characters")
        if set(normalized) == {"0"}:
            raise ValueError("must not be all zeros")
        return normalized

    return BeforeValidator(validate)


Timestamp = Annotated[datetime | None, BeforeValidator(_nanos_to_datetime)]
TraceId = Annotated[str | None, _hex_id(32)]
SpanId = Annotated[str | None, _hex_id(16)]


class KeyValue(OtlpModel):
    key: str
    value: dict[str, Any] = Field(default_factory=dict)


class Resource(OtlpModel):
    attributes: list[KeyValue] = Field(default_factory=list)


class Scope(OtlpModel):
    name: str = ""
    version: str = ""


# Traces


class SpanStatus(OtlpModel):
    code: int = 0
    message: str = ""


class Span(OtlpModel):
    traceId: TraceId = None
    spanId: SpanId = None
    parentSpanId: SpanId = None
    name: str = ""
    kind: int = 0
    startTimeUnixNano: Timestamp = None
    endTimeUnixNano: Timestamp = None
    attributes: list[KeyValue] = Field(default_factory=list)
    status: SpanStatus | None = None


class ScopeSpans(OtlpModel):
    scope: Scope | None = None
    spans: list[dict[str, Any]] = Field(default_factory=list)


class ResourceSpans(OtlpModel):
    resource: Resource | None = None
    scopeSpans: list[ScopeSpans] = Field(default_factory=list)


class ExportTraceRequest(OtlpModel):
    resourceSpans: list[ResourceSpans] = Field(default_factory=list)


# Metrics


class NumberDataPoint(OtlpModel):
    timeUnixNano: Timestamp = None
    startTimeUnixNano: Timestamp = None
    asDouble: float | None = None
    asInt: int | None = None
    attributes: list[KeyValue] = Field(default_factory=list)


class SummaryDataPoint(OtlpModel):
    """Also covers histogram and exponential histogram points (we read count/sum only)."""

    timeUnixNano: Timestamp = None
    startTimeUnixNano: Timestamp = None
    count: int | None = None
    sum: float | None = None
    attributes: list[KeyValue] = Field(default_factory=list)


class ScopeMetrics(OtlpModel):
    scope: Scope | None = None
    metrics: list[dict[str, Any]] = Field(default_factory=list)


class ResourceMetrics(OtlpModel):
    resource: Resource | None = None
    scopeMetrics: list[ScopeMetrics] = Field(default_factory=list)


class ExportMetricsRequest(OtlpModel):
    resourceMetrics: list[ResourceMetrics] = Field(default_factory=list)


# Logs


class LogRecord(OtlpModel):
    timeUnixNano: Timestamp = None
    observedTimeUnixNano: Timestamp = None
    severityNumber: int = Field(default=0, ge=0, le=24)
    severityText: str = ""
    body: dict[str, Any] | None = None
    attributes: list[KeyValue] = Field(default_factory=list)
    traceId: TraceId = None
    spanId: SpanId = None
    eventName: str = ""


class ScopeLogs(OtlpModel):
    scope: Scope | None = None
    logRecords: list[dict[str, Any]] = Field(default_factory=list)


class ResourceLogs(OtlpModel):
    resource: Resource | None = None
    scopeLogs: list[ScopeLogs] = Field(default_factory=list)


class ExportLogsRequest(OtlpModel):
    resourceLogs: list[ResourceLogs] = Field(default_factory=list)
