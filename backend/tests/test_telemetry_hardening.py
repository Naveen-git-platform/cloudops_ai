"""Adversarial and robustness tests for OTLP/HTTP ingestion.

These complement test_telemetry.py: protocol edge cases, malformed input,
limits, duplicates, concurrency and database failures. Every test checks the
database directly where it matters, so accepted counts can't drift from what
is actually stored.
"""

import gzip
import json
import math
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from google.protobuf.json_format import Parse
from google.rpc import status_pb2
from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
    ExportTraceServiceRequest,
    ExportTraceServiceResponse,
)
from sqlalchemy import exc as sa_exc
from sqlalchemy import text

from app.config import Settings
from app.db import Database
from app.main import create_app
from app.telemetry.repository import TelemetryRepository
from tests.otlp_helpers import (
    FIXTURE_COUNTS,
    JSON,
    PROTOBUF,
    T0,
    T0_NANOS,
    TRACE_ID,
    fixture,
    gauge,
    kv,
    logs_payload,
    metrics_payload,
    nanos,
    post_json,
    records,
    row_count,
    span,
    to_protobuf,
    traces_payload,
    ts,
)

SIGNALS = ["traces", "metrics", "logs"]
SPAN = span("00000000000000a1")
TEN_MIB = 10 * 1024 * 1024


def error_status(response) -> tuple[int, str]:
    """Decode an OTLP error body (google.rpc.Status) in the response's encoding."""
    content_type = response.headers["content-type"]
    if content_type.startswith("application/x-protobuf"):
        status = status_pb2.Status.FromString(response.content)
    else:
        assert content_type.startswith("application/json"), content_type
        status = Parse(response.text, status_pb2.Status())
    return status.code, status.message


def rejected(response, field: str) -> int:
    return int(response.json().get("partialSuccess", {}).get(field, 0))


def deep_array(depth: int) -> dict[str, Any]:
    value: dict[str, Any] = {"stringValue": "leaf"}
    for _ in range(depth):
        value = {"arrayValue": {"values": [value]}}
    return value


# 1-3. Valid payloads in every encoding


@pytest.mark.parametrize("signal", SIGNALS)
@pytest.mark.parametrize("encoding", ["json", "protobuf"])
@pytest.mark.parametrize("compressed", [False, True], ids=["plain", "gzip"])
def test_valid_payloads_every_encoding(client: TestClient, database: Database, signal, encoding, compressed):
    body = json.dumps(fixture(signal)).encode() if encoding == "json" else to_protobuf(signal, fixture(signal))
    headers = dict(JSON if encoding == "json" else PROTOBUF)
    if compressed:
        body = gzip.compress(body)
        headers["Content-Encoding"] = "gzip"

    response = client.post(f"/v1/{signal}", content=body, headers=headers)

    assert response.status_code == 200
    assert response.headers["content-type"] == headers["Content-Type"]
    assert row_count(database.engine, signal=signal) == FIXTURE_COUNTS[signal]


@pytest.mark.parametrize(
    "content_type", ["application/json; charset=utf-8", "Application/JSON", "APPLICATION/X-PROTOBUF"]
)
def test_content_type_parameters_and_case_are_accepted(client: TestClient, content_type: str):
    body = to_protobuf("logs", fixture("logs")) if "PROTOBUF" in content_type else json.dumps(fixture("logs"))
    assert client.post("/v1/logs", content=body, headers={"Content-Type": content_type}).status_code == 200


# 4-8, 29. Malformed requests get OTLP-compliant error bodies


@pytest.mark.parametrize("signal", SIGNALS)
@pytest.mark.parametrize(
    ("headers", "body", "status"),
    [
        (JSON, b"{not json", 400),
        (JSON, b"[]", 400),
        (JSON, b'{"x": NaN}', 400),
        (JSON, b"\xff\xfe\xfd", 400),
        (PROTOBUF, b"\xff\xff\xff\xff", 400),
        ({**PROTOBUF, "Content-Encoding": "gzip"}, b"not gzip", 400),
        ({**JSON, "Content-Encoding": "gzip"}, b"not gzip", 400),
        ({**JSON, "Content-Encoding": "br"}, b"{}", 415),
        ({**PROTOBUF, "Content-Encoding": "deflate"}, b"", 415),
    ],
)
def test_malformed_requests_return_status_in_request_encoding(client, database, signal, headers, body, status):
    response = client.post(f"/v1/{signal}", content=body, headers=headers)

    assert response.status_code == status
    assert response.headers["content-type"] == headers["Content-Type"]
    code, message = error_status(response)
    assert code != 0
    assert message
    assert row_count(database.engine) == 0


@pytest.mark.parametrize("content_type", [None, "text/plain", "application/xml", "application/protobuf"])
def test_unsupported_content_type_is_415_with_json_status(client: TestClient, content_type: str | None):
    headers = {"Content-Type": content_type} if content_type else {}
    response = client.post("/v1/traces", content=b"{}", headers=headers)
    assert response.status_code == 415
    _code, message = error_status(response)  # no usable request encoding, so JSON
    assert "Content-Type" in message


def test_invalid_utf8_in_protobuf_string_is_rejected(client: TestClient, database: Database):
    request = ExportTraceServiceRequest()
    request.resource_spans.add().scope_spans.add().spans.add().name = "QZ"
    body = request.SerializeToString().replace(b"QZ", b"\xff\xfe")
    response = client.post("/v1/traces", content=body, headers=PROTOBUF)
    assert response.status_code == 400
    assert error_status(response)[0] != 0


def test_wrong_method_and_unknown_signal(client: TestClient):
    assert client.get("/v1/traces").status_code == 405
    assert client.post("/v1/profiles", content=b"{}", headers=JSON).status_code == 404


# 9. Empty bodies


@pytest.mark.parametrize("signal", SIGNALS)
@pytest.mark.parametrize("headers", [JSON, PROTOBUF], ids=["json", "protobuf"])
def test_empty_body_is_an_empty_export(client: TestClient, database: Database, signal, headers):
    response = client.post(f"/v1/{signal}", content=b"", headers=headers)
    assert response.status_code == 200
    assert row_count(database.engine) == 0


def test_gzip_of_empty_body(client: TestClient):
    response = client.post("/v1/logs", content=gzip.compress(b""), headers={**PROTOBUF, "Content-Encoding": "gzip"})
    assert response.status_code == 200


# 10. Structurally invalid OTLP


@pytest.mark.parametrize(
    "payload",
    [
        {"resourceSpans": "nope"},
        {"resourceSpans": [1]},
        {"resourceSpans": [{"scopeSpans": "nope"}]},
        {"resourceSpans": [{"scopeSpans": [{"spans": [1, 2]}]}]},
        {"resourceSpans": [{"resource": {"attributes": "nope"}}]},
        {"resourceSpans": [{"resource": {"attributes": [{"key": 1}]}}]},
        # Malformed AnyValues in resource attributes (with a span, so the resource is read)
        *(
            {
                "resourceSpans": [
                    {"resource": {"attributes": [{"key": "a", "value": bad}]}, "scopeSpans": [{"spans": [SPAN]}]}
                ]
            }
            for bad in (
                {"arrayValue": "x"},
                {"kvlistValue": []},
                {"arrayValue": {"values": [5]}},
                {"intValue": "abc"},
                {"stringValue": 7},
            )
        ),
    ],
)
def test_structurally_invalid_requests_are_400_not_500(client: TestClient, database: Database, payload):
    response = post_json(client, "traces", payload)
    assert response.status_code == 400, response.text
    assert row_count(database.engine) == 0


@pytest.mark.parametrize(
    "bad_value",
    [
        {"arrayValue": "x"},
        {"kvlistValue": []},
        {"kvlistValue": {"values": [{"key": 1}]}},
        {"arrayValue": {"values": [5]}},
        {"intValue": "12abc"},
        {"doubleValue": "lots"},
    ],
)
def test_malformed_span_attribute_rejects_only_that_span(client: TestClient, database: Database, bad_value):
    payload = traces_payload(
        [span("00000000000000a1", attributes=[{"key": "bad", "value": bad_value}]), span("00000000000000a2")]
    )
    response = post_json(client, "traces", payload)
    assert response.status_code == 200
    assert rejected(response, "rejectedSpans") == 1
    assert row_count(database.engine) == 1


def test_deeply_nested_json_is_rejected_cleanly(client: TestClient, database: Database):
    body = b'{"resourceSpans": ' + b"[" * 100_000 + b"]" * 100_000 + b"}"
    response = client.post("/v1/traces", content=body, headers=JSON)
    assert response.status_code == 400
    assert row_count(database.engine) == 0


def test_deeply_nested_attribute_is_rejected_cleanly(client: TestClient, database: Database):
    """Nesting beyond 128 JSON levels fails the request with 400 (real OTLP is ~10-20 levels deep)."""
    payload = traces_payload(
        [span("00000000000000a1", attributes=[{"key": "deep", "value": deep_array(300)}]), span("00000000000000a2")]
    )
    response = post_json(client, "traces", payload)
    assert response.status_code == 400
    assert "nested" in error_status(response)[1]
    assert row_count(database.engine) == 0


def test_moderately_nested_attribute_is_accepted(client: TestClient, database: Database):
    payload = traces_payload([span("00000000000000a1", attributes=[{"key": "deep", "value": deep_array(20)}])])
    assert post_json(client, "traces", payload).status_code == 200
    assert row_count(database.engine) == 1


def test_metric_with_unknown_or_invalid_data_is_counted_not_dropped(client: TestClient, database: Database):
    payload = metrics_payload(
        [
            {"name": "future.metric", "someNewType": {"dataPoints": [{"timeUnixNano": nanos(), "asDouble": 1}]}},
            {"name": "broken.gauge", "gauge": 5},
            {"name": "broken.points", "gauge": {"dataPoints": {"timeUnixNano": nanos()}}},
            {"name": "empty.gauge", "gauge": {"dataPoints": []}},  # valid: nothing to store
            gauge("ok.gauge", (0, 1.0)),
        ]
    )
    response = post_json(client, "metrics", payload)
    assert response.status_code == 200
    assert rejected(response, "rejectedDataPoints") == 3
    assert row_count(database.engine) == 1


def test_snake_case_json_keys_are_ignored_per_spec(client: TestClient, database: Database):
    """OTLP/JSON requires lowerCamelCase keys and receivers MUST ignore unknown fields."""
    response = post_json(
        client, "traces", {"resource_spans": [{"scope_spans": [{"spans": [span("00000000000000a1")]}]}]}
    )
    assert response.status_code == 200
    assert row_count(database.engine) == 0


def test_enum_names_are_rejected_per_spec(client: TestClient, database: Database):
    """OTLP/JSON requires integer enums; names are rejected for that record only."""
    response = post_json(client, "traces", traces_payload([span("00000000000000a1", kind="SPAN_KIND_SERVER")]))
    assert rejected(response, "rejectedSpans") == 1


# 11. service.name


@pytest.mark.parametrize(
    ("attributes", "expected"),
    [
        ([], "unknown_service"),
        ([kv("service.name", "")], "unknown_service"),
        ([kv("service.name", "   ")], "unknown_service"),
        ([kv("service.name", "  checkout-api  ")], "checkout-api"),
        ([kv("service.name", 123)], "123"),
    ],
)
def test_service_name_normalisation(client: TestClient, attributes, expected):
    payload = {
        "resourceLogs": [
            {"resource": {"attributes": attributes}, "scopeLogs": [{"logRecords": [{"timeUnixNano": nanos()}]}]}
        ]
    }
    assert post_json(client, "logs", payload).status_code == 200
    assert [r["service_name"] for r in records(client)] == [expected]


# 12. Trace and span IDs


@pytest.mark.parametrize(
    "fields",
    [
        {"traceId": "abc"},
        {"traceId": "zz" * 16},
        {"traceId": "0" * 32},
        {"traceId": TRACE_ID + "00"},
        {"spanId": "123"},
        {"spanId": "0" * 16},
        {"spanId": "g" * 16},
        {"parentSpanId": "123"},
        {"parentSpanId": "0" * 16},
        {"traceId": 12345},
    ],
)
def test_invalid_ids_reject_the_span(client: TestClient, database: Database, fields):
    payload = traces_payload([{**span("00000000000000a1"), **fields}, span("00000000000000a2")])
    response = post_json(client, "traces", payload)
    assert response.status_code == 200
    assert rejected(response, "rejectedSpans") == 1
    assert row_count(database.engine) == 1


def test_wrong_length_ids_in_protobuf_are_rejected(client: TestClient, database: Database):
    request = ExportTraceServiceRequest()
    s = request.resource_spans.add().scope_spans.add().spans.add()
    s.trace_id, s.span_id, s.start_time_unix_nano = b"\x01" * 10, b"\x02" * 8, T0_NANOS
    response = client.post("/v1/traces", content=request.SerializeToString(), headers=PROTOBUF)
    assert response.status_code == 200
    assert ExportTraceServiceResponse.FromString(response.content).partial_success.rejected_spans == 1
    assert row_count(database.engine) == 0


def test_uppercase_ids_are_normalised(client: TestClient):
    payload = traces_payload([span("00000000000000AB", trace_id=TRACE_ID.upper(), parentSpanId="00000000000000CD")])
    post_json(client, "traces", payload)
    [stored] = records(client)
    assert (stored["trace_id"], stored["span_id"], stored["parent_span_id"]) == (
        TRACE_ID,
        "00000000000000ab",
        "00000000000000cd",
    )


def test_missing_ids_are_stored_as_null(client: TestClient):
    """IDs are stored "when available"; a span without them is kept."""
    raw = span("00000000000000a1")
    del raw["traceId"], raw["spanId"]
    assert rejected(post_json(client, "traces", traces_payload([raw])), "rejectedSpans") == 0
    [stored] = records(client)
    assert stored["trace_id"] is None and stored["span_id"] is None


def test_log_with_invalid_trace_id_is_rejected(client: TestClient, database: Database):
    payload = logs_payload([{"timeUnixNano": nanos(), "traceId": "nope"}, {"timeUnixNano": nanos()}])
    assert rejected(post_json(client, "logs", payload), "rejectedLogRecords") == 1
    assert row_count(database.engine) == 1


# 13. Timestamps


@pytest.mark.parametrize(
    "start",
    [None, "0", 0, "-1", "abc", 1.5e18, "1e18", True, str(2**64), "9" * 5000],
    ids=["missing", "zero-str", "zero", "negative", "text", "float", "exponent", "bool", "over-uint64", "huge"],
)
def test_invalid_span_start_time_rejects_span(client: TestClient, database: Database, start):
    raw = span("00000000000000a1")
    if start is None:
        del raw["startTimeUnixNano"]
    else:
        raw["startTimeUnixNano"] = start
    response = post_json(client, "traces", traces_payload([raw, span("00000000000000a2")]))
    assert response.status_code == 200
    assert rejected(response, "rejectedSpans") == 1
    assert row_count(database.engine) == 1


def test_max_uint64_timestamp_is_accepted(client: TestClient):
    raw = span("00000000000000a1", startTimeUnixNano=str(2**64 - 1))
    assert rejected(post_json(client, "traces", traces_payload([raw])), "rejectedSpans") == 0
    assert records(client)[0]["timestamp"].startswith("2554-07-21")


def test_metric_point_without_time_is_rejected(client: TestClient, database: Database):
    payload = metrics_payload(
        [{"name": "m", "gauge": {"dataPoints": [{"asDouble": 1}, {"timeUnixNano": nanos(), "asDouble": 2}]}}]
    )
    assert rejected(post_json(client, "metrics", payload), "rejectedDataPoints") == 1
    assert row_count(database.engine) == 1


def test_log_without_any_time_uses_receive_time(client: TestClient):
    before = time.time()
    post_json(client, "logs", logs_payload([{"body": {"stringValue": "no clock"}}]))
    [stored] = records(client)
    assert before - 5 < ts(stored["timestamp"]).timestamp() < time.time() + 5
    assert stored["timestamp"] == stored["received_at"]


# 14. Mixed batches


def test_mixed_batch_counts_add_up(client: TestClient, database: Database):
    spans = [span(f"{i + 1:016x}", offset_ms=i) for i in range(20)]
    for i in (2, 5, 9, 14, 17, 19):
        spans[i]["traceId"] = "bad"
    response = post_json(client, "traces", traces_payload(spans))
    assert response.status_code == 200
    assert rejected(response, "rejectedSpans") == 6
    message = response.json()["partialSuccess"]["errorMessage"]
    assert message.count("span:") == 5 and "(and 1 more)" in message  # capped error list
    assert row_count(database.engine) == 14


def test_all_records_invalid_still_200_with_partial_success(client: TestClient, database: Database):
    response = post_json(client, "logs", logs_payload([{"timeUnixNano": nanos(), "severityNumber": 99}] * 3))
    assert response.status_code == 200
    assert rejected(response, "rejectedLogRecords") == 3
    assert row_count(database.engine) == 0


# 15, 27. Duplicates and idempotency


@pytest.mark.parametrize("signal", SIGNALS)
def test_resubmitting_identical_payload_is_idempotent(client: TestClient, database: Database, signal):
    for _ in range(3):
        assert post_json(client, signal, fixture(signal)).status_code == 200
    assert row_count(database.engine) == FIXTURE_COUNTS[signal]


def test_identical_records_within_one_batch_are_stored_once(client: TestClient, database: Database):
    duplicate = span("00000000000000a1")
    assert (
        post_json(client, "traces", traces_payload([duplicate, duplicate, span("00000000000000a2")])).status_code == 200
    )
    assert row_count(database.engine) == 2


def test_same_span_from_different_services_is_not_deduplicated(client: TestClient, database: Database):
    post_json(client, "traces", traces_payload([span("00000000000000a1")], service="a"))
    post_json(client, "traces", traces_payload([span("00000000000000a1")], service="b"))
    assert row_count(database.engine) == 2


def test_cumulative_metric_reexport_at_new_time_is_kept(client: TestClient, database: Database):
    post_json(client, "metrics", metrics_payload([gauge("requests", (0, 10.0))]))
    post_json(client, "metrics", metrics_payload([gauge("requests", (60_000, 10.0))]))
    assert row_count(database.engine) == 2


# 16. Out-of-order timestamps


def test_out_of_order_records_are_stored_and_queried_in_time_order(client: TestClient, database: Database):
    offsets = [500, -2000, 0, 90_000, -1, 30_000]
    post_json(client, "traces", traces_payload([span(f"{i + 1:016x}", offset_ms=o) for i, o in enumerate(offsets)]))
    stored = [ts(r["timestamp"]) for r in records(client)]
    assert len(stored) == 6
    assert stored == sorted(stored, reverse=True)


def test_span_ending_before_it_starts_is_stored_as_sent(client: TestClient):
    raw = span("00000000000000a1", endTimeUnixNano=nanos(-1000))
    assert rejected(post_json(client, "traces", traces_payload([raw])), "rejectedSpans") == 0
    [stored] = records(client)
    assert ts(stored["end_timestamp"]) < ts(stored["timestamp"])


# 17. Large values


def test_oversized_values_are_clipped_in_columns_but_kept_in_raw(client: TestClient, database: Database):
    """VARCHAR columns would make PostgreSQL reject the whole batch; values are clipped instead."""
    long_service = "s" * 300
    payload = {
        "resourceLogs": [
            {
                "resource": {"attributes": [kv("service.name", long_service), kv("host.name", "h" * 400)]},
                "scopeLogs": [
                    {
                        "scope": {"name": "n" * 1000, "version": "v" * 1000},
                        "logRecords": [
                            {
                                "timeUnixNano": nanos(),
                                "severityText": "X" * 100,
                                "eventName": "e" * 5000,
                                "traceId": TRACE_ID,
                            }
                        ],
                    }
                ],
            }
        ]
    }
    response = post_json(client, "logs", payload)
    assert response.status_code == 200, response.text
    [stored] = records(client)
    assert stored["service_name"] == long_service[:255]
    assert len(stored["host_name"]) == 255
    assert len(stored["scope_name"]) == 255
    assert len(stored["severity_text"]) == 32
    assert len(stored["name"]) == 1024
    assert stored["resource_attributes"]["service.name"] == long_service
    assert stored["raw"]["severityText"] == "X" * 100
    assert row_count(database.engine) == 1


def test_long_span_and_metric_names_and_units(client: TestClient):
    post_json(client, "traces", traces_payload([span("00000000000000a1", name="n" * 5000)]))
    metric = {**gauge("m" * 2000, (0, 1.0)), "unit": "u" * 500}
    assert post_json(client, "metrics", metrics_payload([metric])).status_code == 200
    by_signal = {r["signal"]: r for r in records(client)}
    assert len(by_signal["traces"]["name"]) == 1024
    assert len(by_signal["metrics"]["unit"]) == 64
    assert by_signal["metrics"]["raw"]["metric"]["name"] == "m" * 2000


def test_large_body_and_many_attributes(client: TestClient):
    body = "x" * (2 * 1024 * 1024)
    attributes = [kv(f"attr.{i}", "v" * 100) for i in range(2000)]
    payload = logs_payload([{"timeUnixNano": nanos(), "body": {"stringValue": body}, "attributes": attributes}])
    assert post_json(client, "logs", payload).status_code == 200
    [stored] = records(client)
    assert stored["body"] == body
    assert len(stored["attributes"]) == 2000


def test_lone_surrogates_in_json_are_replaced(client: TestClient):
    body = (
        b'{"resourceLogs":[{"scopeLogs":[{"logRecords":[{"timeUnixNano":"1792065600000000000",'
        b'"body":{"stringValue":"a\\ud800b"},"attributes":[{"key":"k\\udfff","value":{"stringValue":"v"}}]}]}]}]}'
    )
    response = client.post("/v1/logs", content=body, headers=JSON)
    assert response.status_code == 200, response.text
    [stored] = records(client)
    assert stored["body"] == "a�b"
    assert list(stored["attributes"]) == ["k�"]


def test_non_finite_and_overflowing_numbers(client: TestClient):
    """1e400 parses to inf in Python; inf isn't valid JSON for PostgreSQL JSONB."""
    body = (
        b'{"resourceMetrics":[{"scopeMetrics":[{"metrics":[{"name":"overflow","gauge":{"dataPoints":'
        b'[{"timeUnixNano":"1792065600000000000","asDouble":1e400,"attributes":[{"key":"d","value":{"doubleValue":-1e400}}]}]}}]}]}]}'
    )
    response = client.post("/v1/metrics", content=body, headers=JSON)
    assert response.status_code == 200, response.text
    [stored] = records(client)
    assert stored["value"] is None
    assert stored["attributes"]["d"] == "-inf"
    assert stored["raw"]["dataPoint"]["asDouble"] == "Infinity"


# 18-19. Size limits


def padded(payload: dict[str, Any], size: int) -> bytes:
    """JSON-encode `payload` and pad with trailing whitespace to exactly `size` bytes."""
    body = json.dumps(payload).encode()
    assert len(body) <= size
    return body + b" " * (size - len(body))


def big_log_payload(target_bytes: int) -> dict[str, Any]:
    payload = logs_payload([{"timeUnixNano": nanos(), "body": {"stringValue": ""}}])
    overhead = len(json.dumps(payload).encode())
    payload["resourceLogs"][0]["scopeLogs"][0]["logRecords"][0]["body"]["stringValue"] = "x" * (target_bytes - overhead)
    return payload


def test_body_exactly_at_the_10mib_limit_is_accepted(client: TestClient, database: Database):
    body = padded(big_log_payload(TEN_MIB - 64), TEN_MIB)
    assert len(body) == TEN_MIB
    response = client.post("/v1/logs", content=body, headers=JSON)
    assert response.status_code == 200
    assert row_count(database.engine) == 1


def test_body_one_byte_over_the_limit_is_413(client: TestClient, database: Database):
    body = padded(big_log_payload(TEN_MIB - 64), TEN_MIB + 1)
    response = client.post("/v1/logs", content=body, headers=JSON)
    assert response.status_code == 413
    assert error_status(response)[1]
    assert row_count(database.engine) == 0


def test_gzip_expanding_to_exactly_the_limit_is_accepted(client: TestClient, database: Database):
    body = gzip.compress(padded(big_log_payload(TEN_MIB - 64), TEN_MIB))
    assert len(body) < 100_000
    response = client.post("/v1/logs", content=body, headers={**JSON, "Content-Encoding": "gzip"})
    assert response.status_code == 200
    assert row_count(database.engine) == 1


def test_gzip_bomb_beyond_the_limit_is_413(client: TestClient, database: Database):
    body = gzip.compress(padded(big_log_payload(1024), TEN_MIB + 1))
    response = client.post("/v1/logs", content=body, headers={**JSON, "Content-Encoding": "gzip"})
    assert response.status_code == 413
    assert row_count(database.engine) == 0


def test_truncated_gzip_is_rejected_not_partially_ingested(client: TestClient, database: Database):
    """A truncated stream can end on a protobuf message boundary and silently drop records."""
    full = to_protobuf("traces", fixture("traces"))
    compressed = gzip.compress(full)
    for cut in (len(compressed) - 8, len(compressed) // 2):
        response = client.post("/v1/traces", content=compressed[:cut], headers={**PROTOBUF, "Content-Encoding": "gzip"})
        assert response.status_code == 400, cut
    assert row_count(database.engine) == 0


def test_multi_member_gzip_is_fully_decoded(client: TestClient, database: Database):
    """gzip allows concatenated members; all of them must be read."""
    full = to_protobuf("traces", fixture("traces"))
    split = len(full) // 2
    body = gzip.compress(full[:split]) + gzip.compress(full[split:])
    response = client.post("/v1/traces", content=body, headers={**PROTOBUF, "Content-Encoding": "gzip"})
    assert response.status_code == 200
    assert row_count(database.engine) == FIXTURE_COUNTS["traces"]


def test_gzip_with_trailing_garbage_is_rejected(client: TestClient, database: Database):
    body = gzip.compress(json.dumps(fixture("logs")).encode()) + b"garbage"
    response = client.post("/v1/logs", content=body, headers={**JSON, "Content-Encoding": "gzip"})
    assert response.status_code == 400
    assert row_count(database.engine) == 0


# 20. Large batches


def test_large_batch_of_twenty_thousand_spans(client: TestClient, database: Database):
    payload = traces_payload([span(f"{i + 1:016x}", offset_ms=i) for i in range(20_000)])
    body = to_protobuf("traces", payload)
    started = time.perf_counter()
    response = client.post("/v1/traces", content=body, headers=PROTOBUF)
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    assert row_count(database.engine) == 20_000
    print(f"\n20k spans ({len(body) / 1e6:.1f} MB protobuf) ingested in {elapsed:.2f}s")


def test_many_resources_in_one_request(client: TestClient, database: Database):
    payload = {
        "resourceLogs": [
            {
                "resource": {"attributes": [kv("service.name", f"svc-{r}")]},
                "scopeLogs": [
                    {"logRecords": [{"timeUnixNano": nanos(i), "body": {"stringValue": f"{r}-{i}"}} for i in range(5)]}
                ],
            }
            for r in range(1000)
        ]
    }
    assert post_json(client, "logs", payload).status_code == 200
    assert row_count(database.engine) == 5000
    assert row_count(database.engine, service_name="svc-999") == 5


# 21. Concurrency


def test_concurrent_ingestion_loses_nothing(client: TestClient, database: Database):
    workers, per_worker, spans_per_request = 8, 5, 50

    def send(worker: int) -> list[int]:
        statuses = []
        for request in range(per_worker):
            base = (worker * per_worker + request) * spans_per_request
            payload = traces_payload(
                [span(f"{base + i + 1:016x}") for i in range(spans_per_request)], service=f"w{worker}"
            )
            statuses.append(
                client.post("/v1/traces", content=to_protobuf("traces", payload), headers=PROTOBUF).status_code
            )
        return statuses

    with ThreadPoolExecutor(workers) as pool:
        statuses = [s for result in pool.map(send, range(workers)) for s in result]

    assert statuses == [200] * workers * per_worker
    assert row_count(database.engine) == workers * per_worker * spans_per_request


def test_concurrent_duplicate_submissions_store_one_copy(client: TestClient, database: Database):
    body = to_protobuf("traces", fixture("traces"))
    barrier = threading.Barrier(8)

    def send(_: int) -> int:
        barrier.wait()
        return client.post("/v1/traces", content=body, headers=PROTOBUF).status_code

    with ThreadPoolExecutor(8) as pool:
        assert list(pool.map(send, range(8))) == [200] * 8
    assert row_count(database.engine) == FIXTURE_COUNTS["traces"]


# 22-23. Database failures


@pytest.fixture
def unavailable_db(tmp_path: Path) -> Iterator[tuple[TestClient, Path]]:
    """An app whose SQLite database directory doesn't exist yet: every connection fails."""
    db_dir = tmp_path / "not-yet"
    settings = Settings(database_url=f"sqlite:///{(db_dir / 'db.sqlite3').as_posix()}", database_auto_create=False, otlp_ingestion_api_key="test-otlp-key")
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        client.headers.update({"X-OTLP-API-Key": "test-otlp-key"})
        yield client, db_dir


@pytest.mark.parametrize("headers", [PROTOBUF, JSON], ids=["protobuf", "json"])
def test_database_unavailable_returns_retryable_503(unavailable_db, headers):
    client, _ = unavailable_db
    body = to_protobuf("logs", fixture("logs")) if headers is PROTOBUF else json.dumps(fixture("logs"))
    response = client.post("/v1/logs", content=body, headers=headers)
    assert response.status_code == 503  # retryable per OTLP/HTTP; 500 would make clients drop data
    assert response.headers["retry-after"].isdigit()
    assert response.headers["content-type"] == headers["Content-Type"]
    code, message = error_status(response)
    assert code == 14  # UNAVAILABLE
    assert "database" in message.lower()


def test_non_telemetry_endpoints_also_report_503_when_database_is_down(unavailable_db):
    client, _ = unavailable_db
    for path in ("/telemetry/records", "/services", "/integrations"):
        response = client.get(path)
        assert response.status_code == 503, path
        assert response.json()["detail"]
    assert client.get("/health").status_code == 200


def test_ingestion_recovers_when_database_returns(unavailable_db):
    client, db_dir = unavailable_db
    body = to_protobuf("traces", fixture("traces"))
    assert client.post("/v1/traces", content=body, headers=PROTOBUF).status_code == 503

    db_dir.mkdir()
    client.app.state.database.create_tables()

    assert client.post("/v1/traces", content=body, headers=PROTOBUF).status_code == 200
    assert client.post("/v1/traces", content=body, headers=PROTOBUF).status_code == 200  # client retry: no duplicates
    assert row_count(client.app.state.database.engine) == FIXTURE_COUNTS["traces"]


@pytest.mark.parametrize(
    "error",
    [
        sa_exc.OperationalError("INSERT", {}, Exception("server closed the connection unexpectedly")),
        sa_exc.InterfaceError("INSERT", {}, Exception("connection already closed")),
        sa_exc.TimeoutError("QueuePool limit of size 5 overflow 10 reached"),
    ],
    ids=["operational", "interface", "pool-timeout"],
)
def test_database_failure_mid_ingestion_is_503_and_writes_nothing(
    client: TestClient, database: Database, monkeypatch: pytest.MonkeyPatch, error
):
    def fail(self, rows):
        raise error

    monkeypatch.setattr(TelemetryRepository, "add_many", fail)
    response = client.post("/v1/traces", content=to_protobuf("traces", fixture("traces")), headers=PROTOBUF)
    assert response.status_code == 503
    assert error_status(response)[0] == 14
    assert row_count(database.engine) == 0

    monkeypatch.undo()
    assert (
        client.post("/v1/traces", content=to_protobuf("traces", fixture("traces")), headers=PROTOBUF).status_code == 200
    )
    assert row_count(database.engine) == FIXTURE_COUNTS["traces"]


def test_unexpected_server_error_returns_otlp_status(settings: Settings, database: Database, monkeypatch):
    def boom(self, rows):
        raise RuntimeError("bug")

    monkeypatch.setattr(TelemetryRepository, "add_many", boom)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        client.headers.update({"X-OTLP-API-Key": "test-otlp-key"})
        response = client.post("/v1/traces", content=to_protobuf("traces", fixture("traces")), headers=PROTOBUF)
    assert response.status_code == 500
    assert error_status(response)[0] == 13  # INTERNAL
    assert "bug" not in error_status(response)[1]  # internals aren't leaked


# 24. Combined query filters


def test_query_with_all_filters_combined(client: TestClient):
    for signal in SIGNALS:
        post_json(client, signal, fixture(signal))
    found = records(
        client,
        service="checkout-api",
        signal="logs",
        trace_id=TRACE_ID,
        start=T0.isoformat(),
        end=(T0.replace(second=1)).isoformat(),
    )
    assert [(r["severity_text"], r["trace_id"]) for r in found] == [("INFO", TRACE_ID)]


# 28. Index usage (PostgreSQL only)


def test_indexes_are_used_for_service_time_and_trace_queries(client: TestClient, database: Database):
    if database.engine.dialect.name != "postgresql":
        pytest.skip("query plans are only meaningful on PostgreSQL")
    payload = {
        "resourceLogs": [
            {
                "resource": {"attributes": [kv("service.name", f"svc-{r}")]},
                "scopeLogs": [
                    {
                        "logRecords": [
                            {
                                "timeUnixNano": nanos(i * 1000),
                                "traceId": f"{r * 1000 + i + 1:032x}",
                                "body": {"stringValue": "x"},
                            }
                            for i in range(200)
                        ]
                    }
                ],
            }
            for r in range(100)
        ]
    }
    assert post_json(client, "logs", payload).status_code == 200
    with database.engine.begin() as connection:
        connection.execute(text("ANALYZE telemetry_records"))
        queries = {
            "ix_telemetry_service_time": "SELECT * FROM telemetry_records WHERE service_name = 'svc-7' "
            "AND timestamp >= now() - interval '100 years' ORDER BY timestamp DESC, id DESC LIMIT 100",
            "ix_telemetry_service_signal_time": "SELECT * FROM telemetry_records WHERE service_name = 'svc-7' "
            "AND signal = 'logs' ORDER BY timestamp DESC, id DESC LIMIT 100",
            "ix_telemetry_trace_id": f"SELECT * FROM telemetry_records WHERE trace_id = '{7001:032x}' "
            "ORDER BY timestamp DESC, id DESC LIMIT 100",
        }
        for index, sql in queries.items():
            plan = json.dumps(connection.execute(text(f"EXPLAIN (FORMAT JSON) {sql}")).scalar_one())
            assert "Index" in plan, (index, plan)
            assert any(
                name in plan
                for name in ("ix_telemetry_service_time", "ix_telemetry_service_signal_time", "ix_telemetry_trace_id")
            ), plan


# 30. Raw preservation


def test_raw_preserves_what_normalisation_discards(client: TestClient):
    payload = traces_payload(
        [
            span(
                "00000000000000a1",
                traceState="vendor=abc",
                flags=769,
                droppedAttributesCount=3,
                events=[{"timeUnixNano": nanos(1), "name": "retry", "attributes": [kv("attempt", 2)]}],
                links=[{"traceId": "0af7651916cd43dd8448eb211c80319c", "spanId": "b7ad6b7169203331"}],
                attributes=[{"key": "blob", "value": {"bytesValue": "AQID"}}],
                futureField={"nested": [1, 2, 3]},
                startTimeUnixNano=str(T0_NANOS + 123_456_789),
            )
        ]
    )
    post_json(client, "traces", payload)
    hist = {
        "name": "latency",
        "unit": "ms",
        "histogram": {
            "aggregationTemporality": 1,
            "dataPoints": [
                {
                    "startTimeUnixNano": nanos(-60_000),
                    "timeUnixNano": nanos(),
                    "count": "3",
                    "sum": 30.5,
                    "min": 1.5,
                    "max": 20,
                    "bucketCounts": ["1", "1", "1"],
                    "explicitBounds": [5, 10],
                    "exemplars": [
                        {"timeUnixNano": nanos(), "asDouble": 20, "traceId": TRACE_ID, "spanId": "00000000000000a1"}
                    ],
                    "flags": 0,
                }
            ],
        },
    }
    post_json(client, "metrics", metrics_payload([hist]))
    log = {"timeUnixNano": str(T0_NANOS + 1), "observedTimeUnixNano": nanos(5), "flags": 1, "droppedAttributesCount": 2}
    post_json(client, "logs", logs_payload([log]))

    stored = {r["signal"]: r for r in records(client)}
    raw_span = stored["traces"]["raw"]
    assert raw_span["traceState"] == "vendor=abc"
    assert raw_span["flags"] == 769
    assert raw_span["droppedAttributesCount"] == 3
    assert raw_span["events"][0]["name"] == "retry"
    assert raw_span["links"][0]["spanId"] == "b7ad6b7169203331"
    assert raw_span["futureField"] == {"nested": [1, 2, 3]}
    assert raw_span["startTimeUnixNano"].endswith("123456789")  # column is microsecond precision
    assert stored["traces"]["attributes"]["blob"] == "AQID"

    raw_point = stored["metrics"]["raw"]
    assert raw_point["metric"]["aggregationTemporality"] == 1
    assert raw_point["dataPoint"]["bucketCounts"] == ["1", "1", "1"]
    assert raw_point["dataPoint"]["exemplars"][0]["traceId"] == TRACE_ID
    assert stored["metrics"]["value"] == 30.5

    raw_log = stored["logs"]["raw"]
    assert raw_log["timeUnixNano"] == str(T0_NANOS + 1)  # 1 ns precision preserved
    assert raw_log["observedTimeUnixNano"] == nanos(5)
    assert raw_log["flags"] == 1
    assert math.isclose(ts(stored["logs"]["timestamp"]).timestamp(), T0.timestamp())


def test_unreachable_postgres_fails_fast_with_503():
    """Without a connect timeout an unreachable database hangs requests for minutes."""
    settings = Settings(
        # 10.255.255.1 is non-routable: SYNs are dropped, like a partitioned database host.
        database_url="postgresql+psycopg://user:pw@10.255.255.1:5432/cloudops",
        database_auto_create=False,
        database_connect_timeout=1,
        otlp_ingestion_api_key="test-otlp-key",
    )
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        started = time.perf_counter()
        response = client.post("/v1/traces", content=to_protobuf("traces", fixture("traces")), headers=PROTOBUF)
        elapsed = time.perf_counter() - started
    assert response.status_code == 503
    assert error_status(response)[0] == 14
    assert elapsed < 10
