from datetime import datetime

from pydantic import BaseModel

from app.models.enums import IntegrationStatus, IntegrationType


class Integration(BaseModel):
    """An external system a service depends on (e.g. Stripe, PostgreSQL, GitHub).

    Holds metadata only; credentials and live connections arrive in later issues.
    """

    id: str
    name: str
    type: IntegrationType
    status: IntegrationStatus
    service_id: str
    created_at: datetime
