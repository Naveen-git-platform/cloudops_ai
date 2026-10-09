from pydantic import BaseModel

from app.models.enums import IntegrationStatus, IntegrationType
from app.schemas.common import STRICT_INPUT, Name, ResourceId


class IntegrationCreate(BaseModel):
    """Request body for POST /integrations."""

    model_config = STRICT_INPUT

    id: ResourceId | None = None
    name: Name
    type: IntegrationType
    status: IntegrationStatus = IntegrationStatus.PENDING
    service_id: ResourceId
