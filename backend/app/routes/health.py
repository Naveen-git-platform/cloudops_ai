import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.config import SERVICE_NAME, VERSION

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness check: confirm the API process can respond."""
    return {"status": "healthy", "service": SERVICE_NAME, "version": VERSION}


@router.get("/ready", response_model=None)
def readiness(request: Request) -> dict[str, str] | JSONResponse:
    """Readiness check: confirm the API can reach its database dependency."""
    database = request.app.state.database
    try:
        with database.engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError as error:
        # Avoid returning database URLs, driver messages, or credentials to callers.
        logger.warning("Readiness check failed: database unavailable (%s)", type(error).__name__)
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "service": SERVICE_NAME,
                "version": VERSION,
                "database": "unavailable",
            },
        )

    return {
        "status": "ready",
        "service": SERVICE_NAME,
        "version": VERSION,
        "database": "available",
    }
