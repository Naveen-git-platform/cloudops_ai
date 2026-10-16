"""Turn OTLP export requests into `telemetry_records` rows.

Each span, metric data point and log record becomes one row. A record that
can't be read is skipped and counted, so the caller can report OTLP partial
success instead of rejecting the whole batch. A malformed envelope raises
`ValueError` (pydantic's `ValidationError` is one).
"""

import hashlib
import json
import math
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from app.telemetry.otlp import Signal
from app.telemetry.schemas import (
    ExportLogsRequest,
    ExportMetricsRequest,
    ExportTraceRequest,
    KeyValue,
    LogRecord,
    NumberDataPoint,
    Resource,
    Scope,
    Span,
    SummaryDataPoint,
)

UNKNOWN_SERVICE = "unknown_service"
MAX_REPORTED_ERRORS = 5
# Deeper requests are rejected: real OTLP payloads are far shallower (about
# 10-20 levels; each AnyValue array level adds 3), and unbounded nesting would
# hit Python's recursion limit.
MAX_NESTING_DEPTH = 128

_SPAN_KINDS = {0: "unspecified", 1: "internal", 2: "server", 3: "client", 4: "producer", 5: "consumer"}
_STATUS_CODES = {0: "unset", 1: "ok", 2: "error"}
_SEVERITY_TEXT = ["TRACE", "DEBUG", "INFO", "WARN", "ERROR", "FATAL"]
# OTLP/JSON key -> stored metric_type
_METRIC_TYPES = {
    "gauge": "gauge",
    "sum": "sum",
    "histogram": "histogram",
    "exponentialHistogram": "exponential_histogram",
    "summary": "summary",
}

Row = dict[str, Any]


@dataclass
class NormalizedBatch:
    rows: list[Row] = field(default_factory=list)
    rejected: int = 0
    errors: list[str] = field(default_factory=list)

    def add[**P](self, what: str, build: Callable[P, Row], *args: P.args, **kwargs: P.kwargs) -> None:
        """Append the row from `build(*args, **kwargs)`, or count the record as rejected if it's invalid."""
        try:
            row = build(*args, **kwargs)
            row["fingerprint"] = fingerprint(row)
        except (ValueError, TypeError) as error:
            self.rejected += 1
            if len(self.errors) < MAX_REPORTED_ERRORS:
                self.errors.append(f"{what}: {_describe(error)}")
        else:
            self.rows.append(row)

    @property
    def error_message(self) -> str:
        more = self.rejected - len(self.errors)
        return "; ".join(self.errors) + (f" (and {more} more)" if more > 0 else "")


def _describe(error: Exception) -> str:
    if isinstance(error, ValidationError):
        return "; ".join(f"{'.'.join(map(str, e['loc']))} {e['msg']}".strip() for e in error.errors())
    return str(error)


def prepare_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Check nesting depth, then make every string and number storable. Runs once per request."""
    if _depth(payload) > MAX_NESTING_DEPTH:
        raise ValueError(f"payload is nested more than {MAX_NESTING_DEPTH} levels deep")
    sanitized: dict[str, Any] = _sanitize(payload)
    return sanitized


def _depth(value: Any) -> int:
    """Nesting depth of a JSON value, computed without recursion (stops counting past the limit)."""
    deepest, stack = 0, [(value, 1)]
    while stack:
        item, depth = stack.pop()
        deepest = max(deepest, depth)
        if deepest > MAX_NESTING_DEPTH:
            break
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
    return deepest


_LONE_SURROGATE = re.compile("[\ud800-\udfff]")


def _sanitize(value: Any) -> Any:
    """Make a value storable in PostgreSQL text and JSONB.

    - NUL characters are removed (PostgreSQL rejects them).
    - Lone UTF-16 surrogates, which JSON allows but UTF-8 can't encode, become U+FFFD.
    - Non-finite floats (JSON `1e400` parses to inf) become the strings protobuf's JSON mapping uses.
    """
    if isinstance(value, str):
        value = value.replace("\x00", "")
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            value = _LONE_SURROGATE.sub("\ufffd", value)
        return value
    if isinstance(value, float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else ("Infinity" if value > 0 else "-Infinity")
    if isinstance(value, dict):
        return {_sanitize(k): _sanitize(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize(v) for v in value]
    return value


def fingerprint(row: Row) -> str:
    """Identity of a record for de-duplication: signal, resource, scope and the OTLP record itself.

    Exporters resend whole batches after timeouts and 503s, so an exact resend
    must not create new rows.
    """
    identity = [row["signal"], row["resource_attributes"], row["scope_name"], row["scope_version"], row["raw"]]
    canonical = json.dumps(identity, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# Attributes


def _typed[T](value: Any, expected: type[T], what: str) -> T:
    # bool is an int subclass, but never a valid int/float/str here.
    if not isinstance(value, expected) or (isinstance(value, bool) and expected is not bool):
        raise ValueError(f"{what} has the wrong type")
    return value


def _values(container: Any, what: str) -> list[Any]:
    return _typed(_typed(container, dict, what).get("values", []), list, f"{what}.values")


def any_value(value: Any) -> Any:
    """Convert an OTLP AnyValue to a plain JSON value. Malformed values raise ValueError."""
    if value is None:
        return None
    value = _typed(value, dict, "AnyValue")
    if "stringValue" in value:
        return _typed(value["stringValue"], str, "stringValue")
    if "boolValue" in value:
        return _typed(value["boolValue"], bool, "boolValue")
    if "intValue" in value:
        raw_int = value["intValue"]
        if isinstance(raw_int, bool) or not isinstance(raw_int, int | str):
            raise ValueError("intValue has the wrong type")
        return int(raw_int)
    if "doubleValue" in value:
        raw_double = value["doubleValue"]
        if isinstance(raw_double, bool) or not isinstance(raw_double, int | float | str):
            raise ValueError("doubleValue has the wrong type")
        number = float(raw_double)
        return number if math.isfinite(number) else str(number)
    if "bytesValue" in value:
        return _typed(value["bytesValue"], str, "bytesValue")  # base64, as in OTLP/JSON
    if "arrayValue" in value:
        return [any_value(v) for v in _values(value["arrayValue"], "arrayValue")]
    if "kvlistValue" in value:
        return attributes_to_dict(KeyValue.model_validate(kv) for kv in _values(value["kvlistValue"], "kvlistValue"))
    return None  # an empty AnyValue


def attributes_to_dict(attributes: Iterable[KeyValue]) -> dict[str, Any]:
    return {kv.key: any_value(kv.value) for kv in attributes}


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def resource_columns(resource: Resource | None, scope: Scope | None) -> Row:
    """Normalised resource/scope columns shared by every record in a scope."""
    attrs = attributes_to_dict(resource.attributes) if resource else {}
    return {
        "service_name": _text(attrs.get("service.name")) or UNKNOWN_SERVICE,
        "service_namespace": _text(attrs.get("service.namespace")),
        "service_version": _text(attrs.get("service.version")),
        # Semantic conventions renamed deployment.environment to deployment.environment.name.
        "environment": _text(attrs.get("deployment.environment.name", attrs.get("deployment.environment"))),
        "host_name": _text(attrs.get("host.name")),
        "scope_name": _text(scope.name) if scope else None,
        "scope_version": _text(scope.version) if scope else None,
        "resource_attributes": attrs,
    }


# Traces


def normalize_traces(payload: dict[str, Any], received_at: datetime) -> NormalizedBatch:
    request = ExportTraceRequest.model_validate(prepare_payload(payload))
    batch = NormalizedBatch()
    for resource_spans in request.resourceSpans:
        for scope_spans in resource_spans.scopeSpans:
            context = resource_columns(resource_spans.resource, scope_spans.scope)
            for raw in scope_spans.spans:
                batch.add("span", _span_row, raw, context, received_at)
    return batch


def _span_row(raw: Any, context: Row, received_at: datetime) -> Row:
    span = Span.model_validate(raw)
    if span.startTimeUnixNano is None:
        raise ValueError("startTimeUnixNano is required")
    return {
        **context,
        "signal": Signal.TRACES,
        "timestamp": span.startTimeUnixNano,
        "end_timestamp": span.endTimeUnixNano,
        "received_at": received_at,
        "name": span.name or None,
        "trace_id": span.traceId,
        "span_id": span.spanId,
        "parent_span_id": span.parentSpanId,
        "span_kind": _SPAN_KINDS.get(span.kind, "unspecified"),
        "status_code": _STATUS_CODES.get(span.status.code if span.status else 0, "unset"),
        "attributes": attributes_to_dict(span.attributes),
        "raw": raw,
    }


# Metrics


def normalize_metrics(payload: dict[str, Any], received_at: datetime) -> NormalizedBatch:
    request = ExportMetricsRequest.model_validate(prepare_payload(payload))
    batch = NormalizedBatch()
    for resource_metrics in request.resourceMetrics:
        for scope_metrics in resource_metrics.scopeMetrics:
            context = resource_columns(resource_metrics.resource, scope_metrics.scope)
            for metric in scope_metrics.metrics:
                name = metric.get("name")
                if not isinstance(name, str) or not name:
                    batch.add("metric", _raise, "name is required")
                    continue
                present = [key for key in _METRIC_TYPES if key in metric]
                if not present:
                    # Count it rather than silently dropping data we can't read.
                    batch.add(f"metric {name}", _raise, "no supported data (" + ", ".join(_METRIC_TYPES) + ")")
                    continue
                for key in present:
                    metric_type, data = _METRIC_TYPES[key], metric[key]
                    points = data.get("dataPoints", []) if isinstance(data, dict) else None
                    if not isinstance(points, list):
                        batch.add(f"metric {name}", _raise, f"{key}.dataPoints must be a list")
                        continue
                    meta = {k: v for k, v in metric.items() if k not in _METRIC_TYPES}
                    meta |= {"type": metric_type} | {k: v for k, v in data.items() if k != "dataPoints"}
                    for raw in points:
                        batch.add(
                            f"metric {name} data point", _metric_row, raw, meta, metric_type, context, received_at
                        )
    return batch


def _metric_row(raw: Any, meta: Row, metric_type: str, context: Row, received_at: datetime) -> Row:
    point: NumberDataPoint | SummaryDataPoint
    if metric_type in ("gauge", "sum"):
        point = NumberDataPoint.model_validate(raw)
        value = point.asDouble if point.asDouble is not None else point.asInt
    else:
        # Histograms and summaries: store the sum; count, buckets and quantiles stay in `raw`.
        point = SummaryDataPoint.model_validate(raw)
        value = point.sum
    if point.timeUnixNano is None:
        raise ValueError("timeUnixNano is required")
    return {
        **context,
        "signal": Signal.METRICS,
        "timestamp": point.timeUnixNano,
        "received_at": received_at,
        "name": meta["name"],
        "metric_type": metric_type,
        "unit": _text(meta.get("unit")),
        "value": float(value) if value is not None and math.isfinite(value) else None,
        "attributes": attributes_to_dict(point.attributes),
        "raw": {"metric": meta, "dataPoint": raw},
    }


def _raise(message: str) -> Row:
    raise ValueError(message)


# Logs


def severity_text_for(number: int) -> str | None:
    """Default text for an OTLP severity number (1-24), per the logs data model."""
    if not 1 <= number <= 24:
        return None
    base = _SEVERITY_TEXT[(number - 1) // 4]
    offset = (number - 1) % 4
    return base if offset == 0 else f"{base}{offset + 1}"


def normalize_logs(payload: dict[str, Any], received_at: datetime) -> NormalizedBatch:
    request = ExportLogsRequest.model_validate(prepare_payload(payload))
    batch = NormalizedBatch()
    for resource_logs in request.resourceLogs:
        for scope_logs in resource_logs.scopeLogs:
            context = resource_columns(resource_logs.resource, scope_logs.scope)
            for raw in scope_logs.logRecords:
                batch.add("log record", _log_row, raw, context, received_at)
    return batch


def _log_row(raw: Any, context: Row, received_at: datetime) -> Row:
    record = LogRecord.model_validate(raw)
    body = any_value(record.body)
    return {
        **context,
        "signal": Signal.LOGS,
        # Event time if set, else when it was observed, else when we received it.
        "timestamp": record.timeUnixNano or record.observedTimeUnixNano or received_at,
        "received_at": received_at,
        "name": record.eventName or None,
        "trace_id": record.traceId,
        "span_id": record.spanId,
        "severity_number": record.severityNumber or None,
        "severity_text": _text(record.severityText) or severity_text_for(record.severityNumber),
        "body": body if body is None or isinstance(body, str) else json.dumps(body, separators=(",", ":")),
        "attributes": attributes_to_dict(record.attributes),
        "raw": raw,
    }


NORMALIZERS: dict[Signal, Callable[[dict[str, Any], datetime], NormalizedBatch]] = {
    Signal.TRACES: normalize_traces,
    Signal.METRICS: normalize_metrics,
    Signal.LOGS: normalize_logs,
}
