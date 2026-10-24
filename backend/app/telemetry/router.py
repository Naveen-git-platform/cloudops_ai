"""OTLP/HTTP ingestion endpoints and a query endpoint for stored telemetry."""

import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.auth import require_authenticated_user
from app.config import Settings
from app.dependencies import get_session
from app.telemetry.normalize import NORMALIZERS
from app.telemetry.otlp import (
    Encoding,
    OtlpError,
    Signal,
    decode_request,
    decompress,
    encode_response,
    parse_content_type,
)
from app.telemetry.repository import TelemetryQuery, TelemetryRepository

logger = logging.getLogger(__name__)

def require_otlp_ingestion_key(
    request: Request,
    supplied_key: Annotated[str | None, Header(alias="X-OTLP-API-Key")] = None,
) -> None:
    """Require a configured shared secret for service-to-service OTLP ingestion."""
    settings: Settings = request.app.state.settings
    expected_key = settings.otlp_ingestion_api_key
    if not expected_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OTLP ingestion authentication is not configured",
        )
    if supplied_key is None or not secrets.compare_digest(supplied_key, expected_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing OTLP ingestion credentials",
            headers={"WWW-Authenticate": 'ApiKey realm="otlp"'},
        )


router = APIRouter(tags=["telemetry"])


@dataclass(frozen=True)
class OtlpBody:
    data: bytes
    encoding: Encoding


async def read_otlp_body(request: Request) -> OtlpBody:
    """Read, size-limit and decompress an OTLP/HTTP request body."""
    settings: Settings = request.app.state.settings
    limit = settings.otlp_max_body_bytes
    encoding = parse_content_type(request.headers.get("content-type"))
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            raise OtlpError(413, f"Request body exceeds {limit} bytes")
        chunks.append(chunk)
    data = decompress(b"".join(chunks), request.headers.get("content-encoding"), limit)
    return OtlpBody(data, encoding)


def get_repository(session: Annotated[Session, Depends(get_session)]) -> TelemetryRepository:
    return TelemetryRepository(session)


BodyDep = Annotated[OtlpBody, Depends(read_otlp_body)]
RepositoryDep = Annotated[TelemetryRepository, Depends(get_repository)]


def _ingest(signal: Signal, body: OtlpBody, repository: TelemetryRepository) -> Response:
    payload = decode_request(signal, body.data, body.encoding)
    try:
        batch = NORMALIZERS[signal](payload, datetime.now(UTC))
    except (ValueError, RecursionError) as error:
        raise OtlpError(400, f"Invalid OTLP {signal} request: {error}") from None
    distinct = repository.add_many(batch.rows)
    if distinct < len(batch.rows):
        logger.debug("Skipped %d duplicate %s records within the batch", len(batch.rows) - distinct, signal)
    return Response(
        content=encode_response(signal, body.encoding, batch.rejected, batch.error_message),
        media_type=body.encoding.value,
    )


_OTLP_DOC = (
    "OTLP/HTTP export endpoint. Accepts `application/x-protobuf` or `application/json`, "
    "optionally `Content-Encoding: gzip`. Responds in the request's encoding; invalid records "
    "are reported via `partialSuccess`."
)


@router.post("/v1/traces", dependencies=[Depends(require_otlp_ingestion_key)], summary="Export traces (OTLP/HTTP)", description=_OTLP_DOC)
def export_traces(body: BodyDep, repository: RepositoryDep) -> Response:
    return _ingest(Signal.TRACES, body, repository)


@router.post("/v1/metrics", dependencies=[Depends(require_otlp_ingestion_key)], summary="Export metrics (OTLP/HTTP)", description=_OTLP_DOC)
def export_metrics(body: BodyDep, repository: RepositoryDep) -> Response:
    return _ingest(Signal.METRICS, body, repository)


@router.post("/v1/logs", dependencies=[Depends(require_otlp_ingestion_key)], summary="Export logs (OTLP/HTTP)", description=_OTLP_DOC)
def export_logs(body: BodyDep, repository: RepositoryDep) -> Response:
    return _ingest(Signal.LOGS, body, repository)


class TelemetryRecordOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    signal: Signal
    service_name: str
    service_namespace: str | None
    service_version: str | None
    environment: str | None
    host_name: str | None
    scope_name: str | None
    scope_version: str | None
    timestamp: datetime
    end_timestamp: datetime | None
    received_at: datetime
    name: str | None
    trace_id: str | None
    span_id: str | None
    parent_span_id: str | None
    span_kind: str | None
    status_code: str | None
    severity_number: int | None
    severity_text: str | None
    body: str | None
    metric_type: str | None
    unit: str | None
    value: float | None
    resource_attributes: dict[str, Any]
    attributes: dict[str, Any]
    raw: dict[str, Any]


def _as_utc(value: datetime | None) -> datetime | None:
    """Treat timestamps without an offset as UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


@router.get("/telemetry/records", response_model=list[TelemetryRecordOut], dependencies=[Depends(require_authenticated_user)])
def list_telemetry_records(
    repository: RepositoryDep,
    service: Annotated[str | None, Query(description="Exact service.name")] = None,
    signal: Signal | None = None,
    start: Annotated[datetime | None, Query(description="Inclusive lower bound (ISO 8601; UTC if no offset)")] = None,
    end: Annotated[datetime | None, Query(description="Exclusive upper bound (ISO 8601; UTC if no offset)")] = None,
    trace_id: Annotated[str | None, Query(pattern=r"^[0-9a-fA-F]{32}$")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
) -> list[TelemetryRecordOut]:
    """Stored telemetry, newest first, filtered by service, signal, time range and trace."""
    start, end = _as_utc(start), _as_utc(end)
    if start is not None and end is not None and start >= end:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "start must be before end")
    records = repository.query(
        TelemetryQuery(service_name=service, signal=signal, start=start, end=end, trace_id=trace_id, limit=limit)
    )
    return [TelemetryRecordOut.model_validate(record) for record in records]
