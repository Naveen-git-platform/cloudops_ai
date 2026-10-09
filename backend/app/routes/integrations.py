from fastapi import APIRouter, status

from app.dependencies import RegistryDep
from app.models import Integration
from app.schemas import IntegrationCreate

router = APIRouter(prefix="/integrations", tags=["integrations"])


@router.get("", response_model=list[Integration])
def list_integrations(registry: RegistryDep, service_id: str | None = None) -> list[Integration]:
    """List integrations, optionally only those for one service."""
    return registry.list_integrations(service_id)


@router.get("/{integration_id}", response_model=Integration)
def get_integration(integration_id: str, registry: RegistryDep) -> Integration:
    return registry.get_integration(integration_id)


@router.post("", response_model=Integration, status_code=status.HTTP_201_CREATED)
def create_integration(payload: IntegrationCreate, registry: RegistryDep) -> Integration:
    return registry.create_integration(payload)
