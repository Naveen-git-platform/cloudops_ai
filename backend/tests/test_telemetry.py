import gzip
import json
from datetime import timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceResponse
from opentelemetry.proto.collector.metrics.v1.metrics_service_pb2 import ExportMetricsServiceResponse
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)
from sqlalchemy import inspect
from sqlalchemy.orm import Session

from app.config import Settings
from app.db import Base, Database
from app.main import create_app
from app.telemetry.otlp import Signal
from app.telemetry.repository import TelemetryQuery, TelemetryRepository
from tests.otlp_helpers import JSON, PROTOBUF, T0, TRACE_ID, fixture, post_json, records, to_protobuf, ts

COMPARED_COLUMNS = [
    "signal",
    "service_name",
    "service_namespace",
    "service_version",
    "environment",
    "host_name",
    "scope_name",
    "scope_version",
    "timestamp",
    "end_timestamp",
    "name",
    "trace_id",
    "span_id",
    "parent_span_id",
    "span_kind",
    "status_code",
    "severity_number",
    "severity_text",
    "body",
    "metric_type",
    "unit",
    "value",
    "resource_attributes",
    "attributes",
]


def comparable(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(({k: r[k] for k in COMPARED_COLUMNS} for r in rows), key=lambda r: json.dumps(r, sort_keys=True))


# Traces


def test_ingest_traces_json(client: TestClient):
    response = post_json(client, "traces", fixture("traces"))
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {}

    spans = records(client, signal="traces")
    assert len(spans) == 3
    server = next(s for s in spans if s["span_id"] == "eee19b7ec3c1b174")
    assert server["service_name"] == "checkout-api"
    assert server["service_namespace"] == "shop"
    assert server["service_version"] == "3.8.1"
    assert server["environment"] == "production"
    assert server["host_name"] == "ip-10-0-1-12"
    assert server["scope_name"] == "opentelemetry.instrumentation.fastapi"
    assert server["name"] == "POST /api/checkout"
    assert server["trace_id"] == TRACE_ID
    assert server["parent_span_id"] is None
    assert server["span_kind"] == "server"
    assert server["status_code"] == "error"
    assert ts(server["timestamp"]) == T0
    assert ts(server["end_timestamp"]) == T0 + timedelta(milliseconds=1240)
    assert server["attributes"]["http.response.status_code"] == 500
    assert server["resource_attributes"]["k8s.pod.name"] == "checkout-api-7d9f8b6c5-x2kqp"
    assert server["raw"]["events"][0]["name"] == "exception"

    child = next(s for s in spans if s["span_id"] == "3c191d03fa8be065")
    assert child["parent_span_id"] == "eee19b7ec3c1b174"
    assert child["span_kind"] == "client"

    payment = next(s for s in spans if s["service_name"] == "payment-service")
    assert payment["status_code"] == "ok"
    assert payment["host_name"] == "ip-10-0-1-34"


def test_ingest_traces_protobuf_matches_json(client: TestClient, database: Database):
    response = client.post("/v1/traces", content=to_protobuf("traces", fixture("traces")), headers=PROTOBUF)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-protobuf"
    assert not ExportTraceServiceResponse.FromString(response.content).HasField("partial_success")
    from_protobuf = records(client, signal="traces")

    # Same payload as OTLP/JSON into empty tables must produce the same rows.
    Base.metadata.drop_all(database.engine)
    Base.metadata.create_all(database.engine)
    assert post_json(client, "traces", fixture("traces")).status_code == 200
    assert comparable(records(client, signal="traces")) == comparable(from_protobuf)


def test_ingest_hand_built_protobuf_span(client: TestClient):
    request = ExportTraceServiceRequest()
    resource_spans = request.resource_spans.add()
    attribute = resource_spans.resource.attributes.add()
    attribute.key, attribute.value.string_value = "service.name", "inventory-worker"
    span = resource_spans.scope_spans.add().spans.add()
    span.trace_id = bytes.fromhex("0af7651916cd43dd8448eb211c80319c")
    span.span_id = bytes.fromhex("b7ad6b7169203331")
    span.name = "reserve-stock"
    span.kind = 5  # SPAN_KIND_CONSUMER
    span.start_time_unix_nano = int(T0.timestamp()) * 10**9 + 123_456_789
    span.end_time_unix_nano = span.start_time_unix_nano + 5_000_000

    response = client.post("/v1/traces", content=request.SerializeToString(), headers=PROTOBUF)
    assert response.status_code == 200
    [stored] = records(client, service="inventory-worker")
    assert stored["trace_id"] == "0af7651916cd43dd8448eb211c80319c"
    assert stored["span_id"] == "b7ad6b7169203331"
    assert stored["span_kind"] == "consumer"
    assert ts(stored["timestamp"]) == T0 + timedelta(microseconds=123_456)  # microsecond precision
    assert stored["raw"]["startTimeUnixNano"] == str(span.start_time_unix_nano)  # exact nanos kept


def test_gzip_compressed_protobuf(client: TestClient):
    body = gzip.compress(to_protobuf("traces", fixture("traces")))
    response = client.post("/v1/traces", content=body, headers={**PROTOBUF, "Content-Encoding": "gzip"})
    assert response.status_code == 200
    assert len(records(client, signal="traces")) == 3


def test_invalid_spans_are_reported_as_partial_success(client: TestClient):
    payload = fixture("traces")
    spans = payload["resourceSpans"][0]["scopeSpans"][0]["spans"]
    spans[0]["traceId"] = "not-a-trace-id"
    del spans[1]["startTimeUnixNano"]

    response = post_json(client, "traces", payload)
    assert response.status_code == 200
    partial = response.json()["partialSuccess"]
    assert partial["rejectedSpans"] == 2
    assert "traceId" in partial["errorMessage"]
    assert "startTimeUnixNano is required" in partial["errorMessage"]
    assert [s["service_name"] for s in records(client, signal="traces")] == ["payment-service"]


def test_partial_success_protobuf_response(client: TestClient):
    payload = fixture("traces")
    del payload["resourceSpans"][0]["scopeSpans"][0]["spans"][0]["startTimeUnixNano"]
    response = client.post("/v1/traces", content=to_protobuf("traces", payload), headers=PROTOBUF)
    assert response.status_code == 200
    parsed = ExportTraceServiceResponse.FromString(response.content)
    assert parsed.partial_success.rejected_spans == 1
    assert "startTimeUnixNano" in parsed.partial_success.error_message


# Metrics


def test_ingest_metrics_json(client: TestClient):
    response = post_json(client, "metrics", fixture("metrics"))
    assert response.status_code == 200
    assert response.json() == {}

    points = records(client, signal="metrics")
    assert len(points) == 4
    histogram = next(p for p in points if p["name"] == "http.server.request.duration")
    assert histogram["metric_type"] == "histogram"
    assert histogram["unit"] == "s"
    assert histogram["value"] == 18.375  # histogram sum
    assert histogram["raw"]["dataPoint"]["bucketCounts"] == ["10", "18", "9", "4", "1"]
    assert histogram["raw"]["metric"]["aggregationTemporality"] == 2
    assert histogram["attributes"]["http.route"] == "/api/checkout"

    active = next(p for p in points if p["name"] == "http.server.active_requests")
    assert active["metric_type"] == "sum"
    assert active["value"] == 12.0
    assert active["raw"]["metric"]["isMonotonic"] is False

    cpu = sorted((p for p in points if p["name"] == "system.cpu.utilization"), key=lambda p: p["timestamp"])
    assert [p["value"] for p in cpu] == [0.83, 0.91]
    assert [ts(p["timestamp"]) for p in cpu] == [T0, T0 + timedelta(seconds=30)]
    assert cpu[0]["scope_name"] == "opentelemetry.instrumentation.system_metrics"


def test_ingest_metrics_protobuf(client: TestClient):
    response = client.post("/v1/metrics", content=to_protobuf("metrics", fixture("metrics")), headers=PROTOBUF)
    assert response.status_code == 200
    assert not ExportMetricsServiceResponse.FromString(response.content).HasField("partial_success")
    values = {p["name"]: p["value"] for p in records(client, signal="metrics") if p["metric_type"] != "gauge"}
    assert values == {"http.server.request.duration": 18.375, "http.server.active_requests": 12.0}


def test_metric_without_name_is_rejected(client: TestClient):
    payload = fixture("metrics")
    del payload["resourceMetrics"][0]["scopeMetrics"][1]["metrics"][0]["name"]
    response = post_json(client, "metrics", payload)
    assert response.status_code == 200
    assert response.json()["partialSuccess"]["rejectedDataPoints"] == 1
    assert len(records(client, signal="metrics")) == 2


# Logs


def test_ingest_logs_json(client: TestClient):
    response = post_json(client, "logs", fixture("logs"))
    assert response.status_code == 200
    assert response.json() == {}

    logs = {log["severity_text"]: log for log in records(client, signal="logs")}
    assert set(logs) == {"ERROR", "INFO", "WARN"}

    error = logs["ERROR"]
    assert error["severity_number"] == 17
    assert error["body"] == "Payment authorization failed: connection pool exhausted"
    assert error["trace_id"] == TRACE_ID
    assert error["span_id"] == "eee19b7ec3c1b174"
    assert error["attributes"]["exception.type"] == "psycopg.OperationalError"
    assert ts(error["timestamp"]) == T0 + timedelta(milliseconds=1230)

    info = logs["INFO"]  # severityText missing: derived from severityNumber 9
    assert info["severity_number"] == 9

    warn = logs["WARN"]  # no timeUnixNano: falls back to observedTimeUnixNano
    assert ts(warn["timestamp"]) == T0 + timedelta(seconds=2)
    assert warn["name"] == "db.pool.saturated"
    assert json.loads(warn["body"]) == {"event": "pool_saturation", "pool.in_use": 20, "pool.max": 20}


def test_ingest_logs_protobuf(client: TestClient):
    response = client.post("/v1/logs", content=to_protobuf("logs", fixture("logs")), headers=PROTOBUF)
    assert response.status_code == 200
    assert not ExportLogsServiceResponse.FromString(response.content).HasField("partial_success")
    assert {log["severity_text"] for log in records(client, signal="logs")} == {"ERROR", "INFO", "WARN"}


def test_missing_service_name_defaults_to_unknown_service(client: TestClient):
    payload = {
        "resourceLogs": [
            {
                "scopeLogs": [
                    {"logRecords": [{"timeUnixNano": "1792065600000000000", "body": {"stringValue": "orphan"}}]}
                ]
            }
        ]
    }
    assert post_json(client, "logs", payload).status_code == 200
    [log] = records(client, signal="logs")
    assert log["service_name"] == "unknown_service"
    assert log["resource_attributes"] == {}


def test_nul_characters_are_stripped(client: TestClient):
    payload = fixture("logs")
    payload["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]["body"] = {"stringValue": "bad\u0000byte"}
    assert post_json(client, "logs", payload).status_code == 200
    assert "badbyte" in {log["body"] for log in records(client, signal="logs")}


# Validation and errors


@pytest.mark.parametrize("signal", ["traces", "metrics", "logs"])
def test_empty_request_is_accepted(client: TestClient, signal: str):
    response = post_json(client, signal, {})
    assert response.status_code == 200
    assert response.json() == {}
    assert records(client) == []


@pytest.mark.parametrize("signal", ["traces", "metrics", "logs"])
def test_valid_gzip_compressed_empty_request_is_accepted(client: TestClient, signal: str):
    response = client.post(
        f"/v1/{signal}",
        content=gzip.compress(b""),
        headers={**JSON, "Content-Encoding": "gzip"},
    )
    assert response.status_code == 200
    assert response.json() == {}
    assert records(client) == []


@pytest.mark.parametrize(
    ("headers", "body", "status"),
    [
        ({}, b"{}", 415),
        ({"Content-Type": "text/plain"}, b"{}", 415),
        ({**JSON, "Content-Encoding": "br"}, b"{}", 415),
        (JSON, b"{not json", 400),
        (JSON, b"[]", 400),
        (JSON, b'{"resourceSpans": "nope"}', 400),
        (JSON, b'{"resourceSpans": [{"scopeSpans": [{"spans": [{"x": NaN}]}]}]}', 400),
        (PROTOBUF, b"\xff\xff\xff\xff", 400),
        ({**PROTOBUF, "Content-Encoding": "gzip"}, b"not gzip", 400),
        ({**JSON, "Content-Encoding": "gzip"}, b"", 400),
    ],
)
def test_invalid_requests_are_rejected(client: TestClient, headers: dict[str, str], body: bytes, status: int):
    response = client.post("/v1/traces", content=body, headers=headers)
    assert response.status_code == status
    # OTLP error body: a google.rpc.Status (JSON here, or when the request encoding is unknown)
    error = response.json() if response.headers["content-type"] == "application/json" else None
    if error is not None:
        assert error["code"] and error["message"]
    assert records(client) == []


def test_oversized_requests_are_rejected(settings: Settings, database: Database):
    small = settings.model_copy(update={"otlp_max_body_bytes": 512})
    with TestClient(create_app(small)) as client:
        big = json.dumps(fixture("traces")).encode()
        assert client.post("/v1/traces", content=big, headers=JSON).status_code == 413
        # A small gzip body that inflates past the limit is refused too.
        bomb = gzip.compress(b"{" + b" " * 100_000 + b"}")
        assert len(bomb) < 512
        response = client.post("/v1/traces", content=bomb, headers={**JSON, "Content-Encoding": "gzip"})
        assert response.status_code == 413


# Querying


@pytest.fixture
def ingested(client: TestClient) -> TestClient:
    for signal in ("traces", "metrics", "logs"):
        assert post_json(client, signal, fixture(signal)).status_code == 200
    return client


def test_query_by_service_and_time_range(ingested: TestClient):
    window = {
        "service": "checkout-api",
        "start": (T0 + timedelta(milliseconds=10)).isoformat(),
        "end": (T0 + timedelta(seconds=2)).isoformat(),
    }
    found = records(ingested, **window)
    # Child span (+15ms), ERROR log (+1230ms); start inclusive, end exclusive (WARN log is at exactly +2s).
    assert {(r["signal"], r["name"] or r["severity_text"]) for r in found} == {
        ("traces", "SELECT payments"),
        ("logs", "ERROR"),
    }
    assert all(r["service_name"] == "checkout-api" for r in found)


def test_query_by_service_signal_and_window_bounds(ingested: TestClient):
    later = records(ingested, service="checkout-api", signal="metrics", start=(T0 + timedelta(seconds=30)).isoformat())
    assert [(r["name"], r["value"]) for r in later] == [("system.cpu.utilization", 0.91)]

    before = records(ingested, service="checkout-api", signal="metrics", end=T0.isoformat())
    assert before == []


def test_query_results_are_newest_first_and_limited(ingested: TestClient):
    found = records(ingested, service="checkout-api")
    stamps = [ts(r["timestamp"]) for r in found]
    assert stamps == sorted(stamps, reverse=True)
    assert len(records(ingested, service="checkout-api", limit=2)) == 2


def test_query_by_trace_id_correlates_services_and_signals(ingested: TestClient):
    found = records(ingested, trace_id=TRACE_ID.upper())
    assert {(r["signal"], r["service_name"]) for r in found} == {
        ("traces", "checkout-api"),
        ("traces", "payment-service"),
        ("logs", "checkout-api"),
    }
    assert len(found) == 5


def test_query_naive_datetimes_are_utc(ingested: TestClient):
    naive_start = (T0 + timedelta(seconds=30)).replace(tzinfo=None).isoformat()
    found = records(ingested, service="checkout-api", signal="metrics", start=naive_start)
    assert len(found) == 1


@pytest.mark.parametrize(
    "params",
    [
        {"start": T0.isoformat(), "end": T0.isoformat()},
        {"signal": "events"},
        {"trace_id": "xyz"},
        {"limit": 0},
        {"limit": 1001},
        {"start": "yesterday"},
    ],
)
def test_query_rejects_invalid_parameters(client: TestClient, params: dict[str, Any]):
    assert client.get("/telemetry/records", params=params).status_code == 422


# Persistence and separation


def test_telemetry_survives_app_restart(settings: Settings, database: Database):
    with TestClient(create_app(settings)) as first:
        post_json(first, "logs", fixture("logs"))
    with TestClient(create_app(settings)) as second:
        assert len(records(second, signal="logs")) == 3


def test_repository_query(ingested: TestClient, database: Database):
    with Session(database.engine) as session:
        repository = TelemetryRepository(session)
        rows = repository.query(
            TelemetryQuery(
                service_name="payment-service", signal=Signal.TRACES, start=T0, end=T0 + timedelta(minutes=1)
            )
        )
        assert [(r.name, r.trace_id, r.timestamp) for r in rows] == [
            ("payments.v1.Payments/Authorize", TRACE_ID, T0 + timedelta(milliseconds=20))
        ]


def test_service_and_time_indexes_exist(database: Database):
    indexes = {ix["name"]: ix["column_names"] for ix in inspect(database.engine).get_indexes("telemetry_records")}
    assert indexes["ix_telemetry_service_time"] == ["service_name", "timestamp"]
    assert indexes["ix_telemetry_service_signal_time"] == ["service_name", "signal", "timestamp"]
    assert indexes["ix_telemetry_trace_id"] == ["trace_id"]


def test_telemetry_does_not_touch_service_registry(ingested: TestClient):
    assert ingested.get("/services").json() == []
    assert ingested.get("/integrations").json() == []
