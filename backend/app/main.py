from fastapi import FastAPI

SERVICE_NAME = "cloudops-api"
VERSION = "0.1.0"

app = FastAPI(title="CloudOps AI API", version=VERSION)


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check for the CloudOps API."""
    return {"status": "healthy", "service": SERVICE_NAME, "version": VERSION}
