from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.config import VERSION
from app.routes import health, integrations, services
from app.services.registry import ConflictError, NotFoundError, Registry, UnknownServiceError


def create_app() -> FastAPI:
    app = FastAPI(title="CloudOps AI API", version=VERSION)
    app.state.registry = Registry()

    app.include_router(health.router)
    app.include_router(services.router)
    app.include_router(integrations.router)

    error_codes = {
        NotFoundError: status.HTTP_404_NOT_FOUND,
        ConflictError: status.HTTP_409_CONFLICT,
        UnknownServiceError: status.HTTP_422_UNPROCESSABLE_CONTENT,
    }
    for error_type, code in error_codes.items():

        def handler(_: Request, exc: Exception, code: int = code) -> JSONResponse:
            return JSONResponse(status_code=code, content={"detail": str(exc)})

        app.add_exception_handler(error_type, handler)

    return app


app = create_app()
