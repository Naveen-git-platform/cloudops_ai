from typing import Annotated

from pydantic import BaseModel, StringConstraints

from app.models.enums import Environment, ServiceStatus
from app.schemas.common import STRICT_INPUT, Name, ResourceId


class ServiceCreate(BaseModel):
    """Request body for POST /services."""

    model_config = STRICT_INPUT

    id: ResourceId | None = None
    name: Name
    description: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] = ""
    environment: Environment
    status: ServiceStatus = ServiceStatus.UNKNOWN
