"""Application-wide error handling.

OTLP endpoints (/v1/...) must answer every 4xx/5xx with a google.rpc.Status in
the request's encoding, and must use retryable status codes for transient
failures (OTLP clients retry 429/502/503/504 only and drop data otherwise).
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse, PlainTextResponse, Response
from sqlalchemy import exc as sa_exc

from app.telemetry.otlp import OtlpError, encode_status, request_encoding

logger = logging.getLogger(__name__)

RETRY_AFTER_SECONDS = 5

# Errors that mean the database can't be reached or is saturated right now.
DATABASE_UNAVAILABLE = (sa_exc.OperationalError, sa_exc.InterfaceError, sa_exc.TimeoutError)


def is_otlp_request(request: Request) -> bool:
    return request.url.path.startswith("/v1/")


def otlp_error(request: Request, http_status: int, message: str, headers: dict[str, str] | None = None) -> Response:
    body, encoding = encode_status(http_status, message, request_encoding(request.headers.get("content-type")))
    return Response(body, status_code=http_status, media_type=encoding.value, headers=headers)


def _otlp_error_handler(request: Request, exc: Exception) -> Response:
    assert isinstance(exc, OtlpError)
    return otlp_error(request, exc.status_code, str(exc))


def _database_unavailable_handler(request: Request, exc: Exception) -> Response:
    logger.warning(
        "Database unavailable while handling %s %s (%s)",
        request.method,
        request.url.path,
        type(exc).__name__,
    )
    message = "The database is temporarily unavailable; retry later"
    headers = {"Retry-After": str(RETRY_AFTER_SECONDS)}
    if is_otlp_request(request):
        return otlp_error(request, status.HTTP_503_SERVICE_UNAVAILABLE, message, headers)
    return JSONResponse({"detail": message}, status_code=status.HTTP_503_SERVICE_UNAVAILABLE, headers=headers)


def _unexpected_error_handler(request: Request, exc: Exception) -> Response:
    # Starlette logs the traceback; keep internals out of the response.
    if is_otlp_request(request):
        return otlp_error(request, status.HTTP_500_INTERNAL_SERVER_ERROR, "Internal server error")
    return PlainTextResponse("Internal Server Error", status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(OtlpError, _otlp_error_handler)
    for error_type in DATABASE_UNAVAILABLE:
        app.add_exception_handler(error_type, _database_unavailable_handler)
    app.add_exception_handler(Exception, _unexpected_error_handler)
