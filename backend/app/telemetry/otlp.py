"""OTLP/HTTP request decoding and response encoding.

Both OTLP/HTTP encodings are supported:

- `application/x-protobuf` (the default for OpenTelemetry SDKs and the Collector)
- `application/json` (OTLP/JSON)

Protobuf payloads are converted to the OTLP/JSON shape so that a single
normaliser handles both. Request bodies may be gzip-compressed.
"""

import base64
import json
import zlib
from enum import StrEnum
from typing import Any

from google.protobuf.json_format import MessageToDict
from google.protobuf.message import DecodeError, Message
from google.rpc import status_pb2  # type: ignore[import-untyped]  # ships .pyi stubs but no py.typed marker
from opentelemetry.proto.collector.logs.v1 import logs_service_pb2
from opentelemetry.proto.collector.metrics.v1 import metrics_service_pb2
from opentelemetry.proto.collector.trace.v1 import trace_service_pb2


class Signal(StrEnum):
    TRACES = "traces"
    METRICS = "metrics"
    LOGS = "logs"


class Encoding(StrEnum):
    JSON = "application/json"
    PROTOBUF = "application/x-protobuf"


class OtlpError(Exception):
    """A request that can't be accepted; `status_code` is the HTTP status to return."""

    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


_REQUEST_TYPES: dict[Signal, type[Message]] = {
    Signal.TRACES: trace_service_pb2.ExportTraceServiceRequest,
    Signal.METRICS: metrics_service_pb2.ExportMetricsServiceRequest,
    Signal.LOGS: logs_service_pb2.ExportLogsServiceRequest,
}

# Byte fields that OTLP/JSON encodes as hex but protobuf's JSON mapping emits as base64.
_ID_FIELDS = frozenset({"traceId", "spanId", "parentSpanId"})


def parse_content_type(header: str | None) -> Encoding:
    media_type = (header or "").split(";", 1)[0].strip().lower()
    try:
        return Encoding(media_type)
    except ValueError:
        raise OtlpError(
            415,
            f"Unsupported Content-Type {media_type or '(missing)'}; use application/x-protobuf or application/json",
        ) from None


def request_encoding(header: str | None) -> Encoding | None:
    """The request's OTLP encoding, or None if the Content-Type isn't one we support."""
    try:
        return parse_content_type(header)
    except OtlpError:
        return None


def decompress(body: bytes, content_encoding: str | None, max_bytes: int) -> bytes:
    """Undo Content-Encoding, refusing payloads that expand beyond `max_bytes`.

    gzip streams may hold several concatenated members; all are read. A
    truncated stream or trailing garbage is an error rather than a silently
    shortened payload.
    """
    encoding = (content_encoding or "identity").strip().lower()
    if encoding == "identity":
        return body
    if encoding != "gzip":
        raise OtlpError(415, f"Unsupported Content-Encoding {encoding}; use gzip or none")

    output = bytearray()
    remaining = body
    while remaining:
        inflater = zlib.decompressobj(wbits=16 + zlib.MAX_WBITS)
        try:
            # max_length must stay >= 1: 0 would mean "unlimited".
            output += inflater.decompress(remaining, max_bytes + 1 - len(output))
        except zlib.error:
            raise OtlpError(400, "Request body is not valid gzip") from None
        if len(output) > max_bytes or inflater.unconsumed_tail:
            raise OtlpError(413, f"Decompressed request body exceeds {max_bytes} bytes")
        if not inflater.eof:
            raise OtlpError(400, "Request body is truncated gzip")
        remaining = inflater.unused_data
    return bytes(output)


def _reject_constant(value: str) -> None:
    raise ValueError(f"invalid JSON number {value}")


def decode_request(signal: Signal, body: bytes, encoding: Encoding) -> dict[str, Any]:
    """Decode an export request into the OTLP/JSON shape."""
    if encoding is Encoding.JSON:
        try:
            payload = json.loads(body or b"{}", parse_constant=_reject_constant)
        except (UnicodeDecodeError, ValueError) as exc:
            raise OtlpError(400, f"Request body is not valid JSON: {exc}") from None
        except RecursionError:
            raise OtlpError(400, "Request body JSON is nested too deeply") from None
        if not isinstance(payload, dict):
            raise OtlpError(400, "Request body must be a JSON object")
        return payload

    message = _REQUEST_TYPES[signal]()
    try:
        message.ParseFromString(body)
    except DecodeError:
        raise OtlpError(400, f"Request body is not a valid protobuf {message.DESCRIPTOR.name}") from None
    result: dict[str, Any] = _ids_to_hex(MessageToDict(message, use_integers_for_enums=True))
    return result


def _ids_to_hex(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: base64.b64decode(item).hex() if key in _ID_FIELDS and isinstance(item, str) else _ids_to_hex(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_ids_to_hex(item) for item in value]
    return value


_REJECTED_FIELD = {
    Signal.TRACES: "rejected_spans",
    Signal.METRICS: "rejected_data_points",
    Signal.LOGS: "rejected_log_records",
}
_RESPONSE_TYPES: dict[Signal, type[Message]] = {
    Signal.TRACES: trace_service_pb2.ExportTraceServiceResponse,
    Signal.METRICS: metrics_service_pb2.ExportMetricsServiceResponse,
    Signal.LOGS: logs_service_pb2.ExportLogsServiceResponse,
}


def encode_response(signal: Signal, encoding: Encoding, rejected: int, error_message: str) -> bytes:
    """Build the Export*ServiceResponse, with partial_success only when records were rejected."""
    field = _REJECTED_FIELD[signal]
    if encoding is Encoding.JSON:
        if not rejected:
            return b"{}"
        camel = "".join(part.capitalize() if i else part for i, part in enumerate(field.split("_")))
        return json.dumps({"partialSuccess": {camel: rejected, "errorMessage": error_message}}).encode()

    response = _RESPONSE_TYPES[signal]()
    if rejected:
        # The generic Message type doesn't declare partial_success; each concrete response does.
        partial: Any = getattr(response, "partial_success")  # noqa: B009
        setattr(partial, field, rejected)
        partial.error_message = error_message
    serialized: bytes = response.SerializeToString()
    return serialized


# Errors. OTLP/HTTP requires 4xx/5xx bodies to be a google.rpc.Status in the
# request's encoding (JSON when the request encoding is unknown).

_GRPC_CODES = {400: 3, 413: 8, 415: 3, 500: 13, 503: 14}  # INVALID_ARGUMENT, RESOURCE_EXHAUSTED, INTERNAL, UNAVAILABLE


def encode_status(http_status: int, message: str, encoding: Encoding | None) -> tuple[bytes, Encoding]:
    """Encode an OTLP error body; returns the body and the encoding used."""
    status = status_pb2.Status(code=_GRPC_CODES.get(http_status, 2), message=message)  # 2 = UNKNOWN
    if encoding is Encoding.PROTOBUF:
        return status.SerializeToString(), Encoding.PROTOBUF
    return json.dumps(MessageToDict(status)).encode(), Encoding.JSON
