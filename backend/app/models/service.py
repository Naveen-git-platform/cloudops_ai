from datetime import datetime

from pydantic import BaseModel

from app.models.enums import Environment, ServiceStatus


class Service(BaseModel):
    """A monitored service as stored by the registry and returned by the API."""

    id: str
    name: str
    description: str
    environment: Environment
    status: ServiceStatus
    created_at: datetime
