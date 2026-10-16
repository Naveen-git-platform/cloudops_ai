from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.config import VERSION, Settings, get_settings
from app.db import Database
from app.errors import register_error_handlers
from app.routes import health, integrations, services
from app.services.registry import ConflictError, NotFoundError, UnknownServiceError
from app.telemetry.router import router as telemetry_router


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Settings are read from the environment at startup unless given."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        config = settings or get_settings()
        database = Database(
            config.database_url, echo=config.database_echo, connect_timeout=config.database_connect_timeout
        )
        if config.database_auto_create:
            database.create_tables()
        database.verify_schema()
        app.state.settings = config
        app.state.database = database
        try:
            yield
        finally:
            database.dispose()

    app = FastAPI(title="CloudOps AI API", version=VERSION, lifespan=lifespan)

    app.include_router(health.router)
    app.include_router(services.router)
    app.include_router(integrations.router)
    app.include_router(telemetry_router)

    error_codes = {
        NotFoundError: status.HTTP_404_NOT_FOUND,
        ConflictError: status.HTTP_409_CONFLICT,
        UnknownServiceError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    }
    for error_type, code in error_codes.items():

        def handler(_: Request, exc: Exception, code: int = code) -> JSONResponse:
            return JSONResponse(status_code=code, content={"detail": str(exc)})

        app.add_exception_handler(error_type, handler)

    register_error_handlers(app)

    return app


app = create_app()
