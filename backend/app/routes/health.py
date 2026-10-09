from fastapi import APIRouter

from app.config import SERVICE_NAME, VERSION

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict[str, str]:
    """Liveness check for the CloudOps API."""
    return {"status": "healthy", "service": SERVICE_NAME, "version": VERSION}
