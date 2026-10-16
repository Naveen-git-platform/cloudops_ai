"""Shared helpers for OTLP ingestion tests."""

import base64
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from google.protobuf.json_format import ParseDict
from google.protobuf.message import Message
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceRequest
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import ExportTraceServiceRequest
from sqlalchemy import Engine, func, select

from app.telemetry.models import TelemetryRecord

FIXTURES = Path(__file__).parent / "fixtures" / "otlp"
TRACE_ID = "5b8efff798038103d269b633813fc60c"
T0 = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)
T0_NANOS = int(T0.timestamp()) * 10**9
JSON = {"Content-Type": "application/json"}
PROTOBUF = {"Content-Type": "application/x-protobuf"}

# Records in each fixture file.
FIXTURE_COUNTS = {"traces": 3, "metrics": 4, "logs": 3}

REQUEST_TYPES: dict[str, type[Message]] = {
    "traces": ExportTraceServiceRequest,
    "metrics": ExportMetricsServiceRequest,
    "logs": ExportLogsServiceRequest,
}


def fixture(name: str) -> dict[str, Any]:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def to_protobuf(signal: str, payload: dict[str, Any]) -> bytes:
    """Encode an OTLP/JSON payload as protobuf (IDs are hex in OTLP/JSON, bytes in protobuf)."""

    def convert(value: Any) -> Any:
        if isinstance(value, dict):
            return {
                k: base64.b64encode(bytes.fromhex(v)).decode()
                if k in ("traceId", "spanId", "parentSpanId")
                else convert(v)
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [convert(v) for v in value]
        return value

    return ParseDict(convert(payload), REQUEST_TYPES[signal]()).SerializeToString()


def post_json(client: TestClient, signal: str, payload: Any):
    return client.post(f"/v1/{signal}", content=json.dumps(payload), headers=JSON)


def records(client: TestClient, **params: Any) -> list[dict[str, Any]]:
    response = client.get("/telemetry/records", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def row_count(engine: Engine, **filters: Any) -> int:
    """Rows actually in the database, bypassing the API."""
    stmt = select(func.count()).select_from(TelemetryRecord)
    for column, value in filters.items():
        stmt = stmt.where(getattr(TelemetryRecord, column) == value)
    with engine.connect() as connection:
        return int(connection.execute(stmt).scalar_one())


def ts(value: str) -> datetime:
    return datetime.fromisoformat(value)


def nanos(offset_ms: float = 0) -> str:
    return str(T0_NANOS + int(offset_ms * 1_000_000))


def kv(key: str, value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"key": key, "value": {"boolValue": value}}
    if isinstance(value, int):
        return {"key": key, "value": {"intValue": str(value)}}
    if isinstance(value, float):
        return {"key": key, "value": {"doubleValue": value}}
    return {"key": key, "value": {"stringValue": value}}


def span(span_id: str, *, trace_id: str = TRACE_ID, offset_ms: float = 0, **extra: Any) -> dict[str, Any]:
    return {
        "traceId": trace_id,
        "spanId": span_id,
        "name": f"span-{span_id}",
        "kind": 2,
        "startTimeUnixNano": nanos(offset_ms),
        "endTimeUnixNano": nanos(offset_ms + 5),
        **extra,
    }


def traces_payload(spans: list[dict[str, Any]], service: str = "checkout-api") -> dict[str, Any]:
    return {
        "resourceSpans": [{"resource": {"attributes": [kv("service.name", service)]}, "scopeSpans": [{"spans": spans}]}]
    }


def logs_payload(log_records: list[dict[str, Any]], service: str = "checkout-api") -> dict[str, Any]:
    return {
        "resourceLogs": [
            {"resource": {"attributes": [kv("service.name", service)]}, "scopeLogs": [{"logRecords": log_records}]}
        ]
    }


def metrics_payload(metrics: list[dict[str, Any]], service: str = "checkout-api") -> dict[str, Any]:
    return {
        "resourceMetrics": [
            {"resource": {"attributes": [kv("service.name", service)]}, "scopeMetrics": [{"metrics": metrics}]}
        ]
    }


def gauge(name: str, *points: tuple[float, float]) -> dict[str, Any]:
    """A gauge metric with (offset_ms, value) data points."""
    return {"name": name, "gauge": {"dataPoints": [{"timeUnixNano": nanos(o), "asDouble": v} for o, v in points]}}
